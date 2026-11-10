// Browser smoke test against the production bundle and a mocked ERPNext API.
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { mkdir, readFile } from 'node:fs/promises'
import { basename, extname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const bundle = fileURLToPath(new URL('../lumenpos/public/pos/', import.meta.url))
const items = [
  ['WP-03', 'Water pump 3 inch', 'Aqua', 'Pumps', 168000],
  ['WP-02', 'Water pump 2 inch', 'Aqua', 'Pumps', 125000],
  ['RT-06', 'Rotary tiller 6 ft', 'FieldPro', 'Tillers', 545000],
  ['PT-07', 'Power tiller 7 HP', 'FieldPro', 'Tillers', 385000],
].map(([name, item_name, brand, item_group, price]) => ({ name, item_name, brand, item_group, price, uom: 'Nos', image: '/product.svg' }))
const customer = { name: 'CUST-001', customer_name: 'Greenfield Farm' }
const user = 'rep@example.test'
const profiles = [{ name: 'Field Sales', company: 'Esafe Demo', currency: 'LKR' }]
const access = { read: true, post: true }
const rows = []
const attempts = []
let paymentKey

function reply(method, args, res) {
  if (method === 'bootstrap') return {
    user, full_name: 'Sam Perera', profiles, can_discount: true, discount_limit: 10,
    discount_approval: 'Passcode only', can_pay: true, can_view_team: true,
    documents: { quotation: access, invoice: access },
  }
  if (method === 'catalog_filters') return { brand: ['Aqua', 'FieldPro'], item_group: ['Pumps', 'Tillers'] }
  if (method === 'catalog') return {
    items: items.filter(item => (!args.brand || item.brand === args.brand) &&
      (!args.item_group || item.item_group === args.item_group) &&
      (!args.search || item.item_name.toLowerCase().includes(args.search.toLowerCase()))),
    price_list: 'Standard Selling', currency: 'LKR', more: false,
  }
  if (method === 'customers') return [customer]
  if (method === 'preview') {
    const base = args.payload.items.reduce((sum, row) => sum + items.find(item => item.name === row.item_code).price * row.qty, 0)
    const discount = base * args.payload.discount / 100
    return { total: base - discount, currency: 'LKR', net_total: base - discount, taxes: 0, discount }
  }
  if (method === 'post_document') {
    const name = args.kind === 'quotation' ? 'QTN-0001' : 'SINV-0001'
    const invoice = args.kind === 'invoice'
    rows.push({
      ...customer, name, owner: user, currency: 'LKR', grand_total: args.payload.reviewed_total,
      docstatus: 1, status: invoice ? 'Unpaid' : 'Open', posting_date: '2026-11-10',
      due_date: args.payload.document_date, outstanding_currency: 'LKR',
      outstanding_amount: invoice ? args.payload.reviewed_total : 0,
    })
    return { name }
  }
  if (method === 'list_documents') return { rows: rows.filter(row => row.name.startsWith(args.kind === 'invoice' ? 'SINV' : 'QTN')), more: false }
  if (method === 'payment_options') return {
    outstanding: rows.find(row => row.name === args.invoice).outstanding_amount,
    currency: 'LKR', modes: [{ name: 'Cash', reference_required: false }],
  }
  if (method === 'record_payment') {
    attempts.push(args.request_key)
    if (paymentKey === args.request_key) return { name: 'PAY-0001' }
    paymentKey = args.request_key
    const row = rows.find(row => row.name === args.invoice)
    row.outstanding_amount -= args.amount
    row.status = 'Partly Paid'
    return { name: 'PAY-0001' }
  }
  if (method === 'check_in') return { creation: '2026-11-10 15:30:00' }
  if (method === 'list_activity') return {
    rows: [{ name: 'visit-1', action: 'Check-in', owner: user, creation: '2026-11-10 15:30:00', latitude: 6.9271, longitude: 79.8612, accuracy: 8 }],
    more: false,
  }
  res.statusCode = 404
  return null
}

const server = createServer(async (req, res) => {
  const path = new URL(req.url, 'http://localhost').pathname
  try {
    if (path.startsWith('/api/method/')) {
      let body = ''
      for await (const chunk of req) body += chunk
      const result = reply(path.split('.').at(-1), JSON.parse(body), res)
      if (!res.destroyed) {
        res.setHeader('Content-Type', 'application/json')
        res.end(JSON.stringify({ message: result }))
      }
      return
    }
    if (path === '/product.svg') {
      res.setHeader('Content-Type', 'image/svg+xml')
      res.end('<svg xmlns="http://www.w3.org/2000/svg" width="320" height="200" viewBox="0 0 320 200"><g stroke="#25334a" stroke-width="8" fill="none"><rect x="42" y="33" width="236" height="140" rx="19"/><path d="M88 173v10m143-10v10"/></g><path fill="#3568d4" d="M86 83h120v68H86z"/><circle cx="195" cy="119" r="42" fill="#10254b"/><circle cx="195" cy="119" r="27" fill="#fff"/><circle cx="195" cy="119" r="13" fill="#68778d"/><path fill="#13a795" d="M80 58h94v31H80z"/></svg>')
      return
    }
    const file = path === '/' || path === '/pos' ? 'index.html' : basename(path)
    const type = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css' }[extname(file)]
    if (type) res.setHeader('Content-Type', type)
    res.end(await readFile(join(bundle, file)))
  } catch {
    res.writeHead(404).end()
  }
})
await new Promise(resolve => server.listen(process.env.SALES_REP_PORT || 0, '127.0.0.1', resolve))
const url = 'http://127.0.0.1:' + server.address().port + '/pos'
console.log('Mock sales workspace', url)
if (process.argv.includes('--serve')) await new Promise(() => {})

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
let browser
try {
  browser = await chromium.launch({
    headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : { channel: 'chrome' }),
  })
  const page = await browser.newPage({
    viewport: { width: 1440, height: 900 },
    geolocation: { latitude: 6.9271, longitude: 79.8612, accuracy: 8 },
    permissions: ['geolocation'],
  })
  page.setDefaultTimeout(10000)
  const errors = []
  page.on('pageerror', e => errors.push(e.message))
  let responseLost = false
  await page.route('**/lumenpos.api.sales_rep.record_payment', async route => {
    const response = await route.fetch()
    if (responseLost) await route.fulfill({ response })
    else {
      // The server committed, but the browser never saw the first response.
      responseLost = true
      await route.abort('failed')
    }
  })
  await page.goto(url)
  await page.getByText('Water pump 3 inch', { exact: true }).waitFor()
  await page.getByLabel('Brand', { exact: true }).selectOption('FieldPro')
  await page.getByText('Rotary tiller 6 ft', { exact: true }).waitFor()
  assert.equal(await page.getByText('Water pump 3 inch', { exact: true }).count(), 0)
  await page.getByLabel('Brand', { exact: true }).selectOption('')
  const pump = page.locator('article').filter({ hasText: 'Water pump 3 inch' })
  await pump.getByRole('button', { name: 'Enlarge photo of Water pump 3 inch' }).click()
  await page.getByRole('dialog', { name: 'Water pump 3 inch' }).waitFor()
  await page.getByRole('button', { name: 'Close photo' }).click()
  async function buildSale() {
    await pump.getByRole('button', { name: '+ Add' }).click()
    await page.getByLabel('Customer', { exact: true }).fill('Greenfield')
    await page.getByRole('button', { name: /Greenfield Farm/ }).click()
    await page.getByLabel('Extra discount (%)').fill('5')
    await page.getByRole('button', { name: 'Review total' }).click()
    await page.getByText(/159,600/).first().waitFor()
  }
  await buildSale()
  await pump.waitFor()
  const output = process.env.SALES_REP_ARTIFACTS
  if (output) {
    await mkdir(output, { recursive: true })
    await page.screenshot({ path: join(output, 'sales-rep-desktop.png') })
    await page.setViewportSize({ width: 390, height: 844 })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), 390)
    await page.screenshot({ path: join(output, 'sales-rep-mobile.png'), fullPage: true })
    await page.setViewportSize({ width: 1440, height: 900 })
  }
  await page.getByRole('button', { name: 'Submit quotation' }).click()
  await page.getByRole('link', { name: 'QTN-0001' }).waitFor()
  console.log('PASS catalog and quotation')
  await page.getByRole('link', { name: 'Catalog', exact: true }).click()
  await page.getByRole('button', { name: 'Invoice', exact: true }).click()
  await buildSale()
  await page.getByLabel('Due date').fill('2026-11-30')
  await page.getByRole('button', { name: 'Review total' }).click()
  await page.getByRole('button', { name: 'Create invoice' }).click()
  await page.getByRole('link', { name: 'SINV-0001' }).waitFor()
  console.log('PASS outstanding invoice')
  await page.getByLabel('Outstanding only').check()
  await page.getByRole('button', { name: 'Record payment' }).click()
  await page.getByLabel('Amount (LKR)').fill('10000')
  await page.getByRole('button', { name: 'Submit payment' }).click()
  await page.getByRole('button', { name: 'Retry payment request' }).click()
  await page.getByText('Partly Paid').waitFor()
  assert.deepEqual(attempts, [paymentKey, paymentKey])
  assert.equal(rows.find(row => row.name === 'SINV-0001').outstanding_amount, 149600)
  console.log('PASS partial payment and retry')
  await page.getByRole('link', { name: 'Activity', exact: true }).click()
  await page.getByRole('button', { name: 'Check in with location' }).click()
  await page.getByText(/Check-in recorded/).waitFor()
  await page.getByText(/6.92710, 79.86120/).waitFor()
  assert.deepEqual(errors, [])
  console.log('PASS catalog, photo, quotation, invoice, payment retry, GPS check-in and mobile width')
} finally {
  await browser?.close()
  server.close()
}
