<!-- Copyright (c) 2026 Esafe (PVT) LTD. SPDX-License-Identifier: AGPL-3.0-only -->
<template>
  <div class="rep">
    <header class="rep-bar">
      <router-link class="rep-brand" to="/">Esafe-<span>SalesRep</span></router-link>
      <nav aria-label="Sales workspace">
        <router-link to="/">Catalog</router-link>
        <router-link v-if="access('quotation', 'read')" to="/quotations">Quotations</router-link>
        <router-link v-if="access('invoice', 'read')" to="/invoices">Invoices</router-link>
        <router-link to="/activity">Activity</router-link>
      </nav>
      <div v-if="setup" class="rep-identity">
        <select v-if="setup.profiles.length > 1" v-model="profileName" aria-label="Sales profile"
          :disabled="!!lines.length || !!payment || !!pending || busy || checkingIn">
          <option v-for="entry in setup.profiles" :key="entry.name">{{ entry.name }}</option>
        </select>
        <span v-else>{{ profileName }}</span>
        <strong>{{ setup.full_name || setup.user }}</strong>
      </div>
    </header>

    <main class="rep-main">
      <p v-if="notice" class="rep-notice" role="status">{{ notice }}</p>
      <p v-if="error" class="rep-error" role="alert">{{ error }}</p>
      <div v-if="pending && !busy" class="rep-notice rep-actions">
        <span>The server did not confirm the result. Retry the same request to check or finish it.</span>
        <button class="rep-primary" @click="sendPending">Retry request</button>
      </div>
      <div v-if="!setup" class="rep-panel rep-empty">
        <h1>Sales Rep</h1>
        <p v-if="!error">Connecting to ERPNext…</p>
        <button v-else @click="loadSetup">Reconnect</button>
      </div>
      <div v-else-if="!profile" class="rep-panel rep-empty">
        <h1>No sales profile available</h1>
        <p>Ask your administrator to assign an enabled POS Profile and grant access to its company.</p>
      </div>

      <div v-else-if="page === 'catalog'" class="rep-workspace">
        <section class="rep-panel rep-catalog" aria-labelledby="catalog-title">
          <div class="rep-heading">
            <div><h1 id="catalog-title">Product catalog</h1><p>{{ catalog.price_list || 'Browse items and selling prices' }}</p></div>
            <button v-if="lines.length" class="rep-jump" @click="orderPanel?.scrollIntoView()">View sale ({{ lines.length }})</button>
          </div>
          <div class="rep-filters">
            <label>Search products<input v-model="query" type="search" placeholder="Item name or code"></label>
            <label>Brand<select v-model="brand" aria-label="Brand"><option value="">All brands</option><option v-for="value in filters.brand" :key="value">{{ value }}</option></select></label>
            <label>Item group<select v-model="group" aria-label="Item group"><option value="">All item groups</option><option v-for="value in filters.item_group" :key="value">{{ value }}</option></select></label>
          </div>
          <p v-if="!catalog.items.length" class="rep-empty" role="status">{{ loading ? 'Loading products…' : 'No products match these filters.' }}</p>
          <div v-else class="rep-products" :aria-busy="loading">
            <article v-for="item in catalog.items" :key="item.name" class="rep-product">
              <button v-if="item.image && !brokenImages.has(item.image)" class="rep-photo"
                :aria-label="'Enlarge photo of ' + item.item_name" @click="openPhoto(item)">
                <img :src="item.image" :alt="item.item_name" loading="lazy" @error="brokenImages.add(item.image)">
              </button>
              <div v-else class="rep-photo rep-no-photo" aria-label="No product photo"><Icon name="image" size="26" /></div>
              <div class="rep-product-body">
                <h2>{{ item.item_name }}</h2>
                <p>{{ item.name }}<template v-if="item.brand"> · {{ item.brand }}</template></p>
                <div class="rep-product-foot">
                  <div><strong>{{ item.price == null ? 'Price unavailable' : money(item.price, catalog.currency) }}</strong><small>{{ item.uom }}</small></div>
                  <button v-if="canSell" class="rep-primary" :disabled="!!pending || busy" @click="add(item)">+ Add</button>
                </div>
              </div>
            </article>
          </div>
          <button v-if="catalog.more" class="rep-more" :disabled="loading" @click="loadPage(true)">Load more products</button>
        </section>

        <section v-if="canSell" ref="orderPanel" class="rep-panel rep-order" aria-labelledby="order-title">
          <div class="rep-heading"><div><h2 id="order-title">New sale</h2><p>Build a quotation or invoice for a customer.</p></div></div>
          <fieldset :disabled="!!pending || busy">
            <div class="rep-switch" aria-label="Document type">
              <button v-if="access('quotation', 'post')" :aria-pressed="kind === 'quotation'" @click="kind = 'quotation'">Quotation</button>
              <button v-if="access('invoice', 'post')" :aria-pressed="kind === 'invoice'" @click="kind = 'invoice'">Invoice</button>
            </div>
            <div class="rep-customer">
              <label>Customer<input v-model="customerSearch" type="search" placeholder="Find a customer" @input="customer = null"></label>
              <ul v-if="!customer && matches.length" class="rep-suggestions" aria-label="Matching customers">
                <li v-for="row in matches" :key="row.name">
                  <button @click="pickCustomer(row)">{{ row.customer_name }} <small>{{ row.name }}</small></button>
                </li>
              </ul>
              <small v-if="!customer && customerSearched && !matches.length">No matching customers.</small>
            </div>
            <div v-if="lines.length" class="rep-lines">
              <div v-for="line in lines" :key="line.name" class="rep-line">
                <div><strong>{{ line.item_name }}</strong><small>{{ line.name }} · {{ line.uom }}</small></div>
                <label>Qty<input v-model.number="line.qty" type="number" min="0.000001" step="any" :aria-label="'Quantity for ' + line.item_name"></label>
                <button class="rep-remove" :aria-label="'Remove ' + line.item_name" @click="lines = lines.filter(item => item.name !== line.name)">×</button>
              </div>
            </div>
            <p v-else class="rep-empty rep-order-empty">Add products to start a sale.</p>
            <div class="rep-order-fields">
              <label>{{ kind === 'quotation' ? 'Valid until' : 'Due date' }}<input v-model="documentDate" type="date"></label>
              <label v-if="setup.can_discount">Extra discount (%)<input v-model.number="discount" type="number" min="0" max="100" step="any"></label>
            </div>
            <label>Internal note <input v-model="note" maxlength="1000" placeholder="Optional"></label>
            <label v-if="requiresPasscode">Manager passcode <input v-model="passcode" type="password" autocomplete="off"></label>
            <p v-if="needsDeskApproval" class="rep-hint">This discount requires approval. Complete it in ERPNext.</p>
            <div class="rep-total">
              <dl v-if="estimate">
                <div><dt>Net total</dt><dd>{{ money(estimate.net_total, estimate.currency) }}</dd></div>
                <div><dt>Taxes</dt><dd>{{ money(estimate.taxes, estimate.currency) }}</dd></div>
                <div v-if="estimate.discount"><dt>Extra discount applied</dt><dd>{{ money(estimate.discount, estimate.currency) }}</dd></div>
                <div><dt>Total</dt><dd>{{ money(estimate.total, estimate.currency) }}</dd></div>
              </dl>
              <p v-else>Review the ERPNext total before submitting.</p>
            </div>
            <div class="rep-actions">
              <button :disabled="!readyToReview" @click="review">{{ reviewing ? 'Calculating…' : 'Review total' }}</button>
              <button class="rep-primary" :disabled="!estimate || !readyToReview || needsDeskApproval || (requiresPasscode && !passcode)"
                @click="saveSale">{{ kind === 'quotation' ? 'Submit quotation' : 'Create invoice' }}</button>
            </div>
          </fieldset>
        </section>
      </div>

      <section v-else class="rep-panel rep-records" aria-labelledby="records-title">
        <div class="rep-heading">
          <div>
            <h1 id="records-title">{{ pageTitle }}</h1>
            <p v-if="page === 'activity'">Check-ins and transactions recorded from this workspace.</p>
            <p v-else>{{ team ? 'Team' : 'Your' }} {{ page }} for {{ profile.company }}.</p>
          </div>
          <button v-if="page === 'activity' && canSell" class="rep-primary" :disabled="checkingIn || busy || !!pending" @click="checkIn">
            {{ checkingIn ? 'Finding location…' : 'Check in with location' }}
          </button>
          <router-link v-else-if="page !== 'activity' && canSell" class="rep-button rep-primary" to="/">New sale</router-link>
        </div>
        <div v-if="page === 'activity'" class="rep-toolbar">
          <p class="rep-hint">Check-in saves your current coordinates and accuracy with your name and the server time.</p>
          <label v-if="setup.can_view_team" class="rep-check"><input v-model="team" type="checkbox"> Show team activity</label>
        </div>
        <div v-else class="rep-toolbar">
          <label>Search documents<input v-model="documentSearch" type="search" placeholder="Number or customer"></label>
          <label v-if="page === 'invoices'">Item code<input v-model="soldItem" type="search" placeholder="Filter items sold"></label>
          <label v-if="page === 'invoices'">Brand<select v-model="soldBrand" aria-label="Brand sold"><option value="">All brands</option><option v-for="value in filters.brand" :key="value">{{ value }}</option></select></label>
          <label v-if="page === 'invoices'" class="rep-check"><input v-model="dueOnly" type="checkbox"> Outstanding only</label>
          <label v-if="setup.can_view_team" class="rep-check"><input v-model="team" type="checkbox"> Show team documents</label>
        </div>
        <p v-if="!records.length" class="rep-empty" role="status">{{ loading ? 'Loading…' : 'No matching records.' }}</p>
        <div v-else class="rep-table" :aria-busy="loading">
          <table v-if="page === 'activity'">
            <thead><tr><th>Server time</th><th>Rep</th><th>Activity</th><th>Document</th><th>Location</th></tr></thead>
            <tbody>
              <tr v-for="row in records" :key="row.name">
                <td>{{ row.creation?.slice(0, 19) }}</td><td>{{ row.sales_person || row.owner }}</td><td>{{ row.action }}</td>
                <td><a v-if="row.reference_name" :href="desk(row.action, row.reference_name)">{{ row.reference_name }}</a><span v-else>—</span></td>
                <td v-if="row.action === 'Check-in'">{{ coordinate(row.latitude) }}, {{ coordinate(row.longitude) }} <small>±{{ Math.round(row.accuracy) }} m</small></td><td v-else>—</td>
              </tr>
            </tbody>
          </table>
          <table v-else>
            <thead><tr><th>Document / Customer</th><th>Date</th><th>{{ page === 'invoices' ? 'Due date' : 'Valid until' }}</th><th>Status</th><th>Total</th><th v-if="page === 'invoices'">Outstanding</th><th>Actions</th></tr></thead>
            <tbody>
              <tr v-for="row in records" :key="row.name">
                <td><a :href="desk(documentType, row.name)">{{ row.name }}</a><small>{{ row.customer_name }}</small></td>
                <td>{{ row.posting_date || row.transaction_date }}</td><td>{{ row.due_date || row.valid_till || '—' }}</td>
                <td><span class="rep-status" :class="{ due: row.outstanding_amount > 0 }">{{ row.status }}</span></td>
                <td>{{ money(row.rounded_total || row.grand_total, row.currency) }}</td>
                <td v-if="page === 'invoices'">{{ money(row.outstanding_amount, row.outstanding_currency) }}</td>
                <td><div class="rep-row-actions">
                  <a v-if="row.docstatus === 1" :href="printLink(documentType, row.name)" target="_blank" rel="noopener">Print</a>
                  <button v-if="page === 'invoices' && setup.can_pay && row.owner === setup.user && row.outstanding_amount > 0 && row.docstatus === 1"
                    :disabled="busy || !!pending || checkingIn" @click="openPayment(row)">Record payment</button>
                </div></td>
              </tr>
            </tbody>
          </table>
        </div>
        <button v-if="recordsMore" class="rep-more" :disabled="loading" @click="loadPage(true)">Load more records</button>
      </section>
    </main>

    <dialog ref="photoDialog" class="rep-dialog" aria-labelledby="photo-title">
      <div v-if="photo" class="rep-photo-dialog">
        <div class="rep-heading"><h2 id="photo-title">{{ photo.item_name }}</h2><button aria-label="Close photo" @click="photoDialog.close()">×</button></div>
        <img :src="photo.image" :alt="photo.item_name">
        <p>{{ photo.name }} · {{ photo.brand || photo.item_group }}</p>
      </div>
    </dialog>

    <dialog ref="paymentDialog" class="rep-dialog" aria-labelledby="payment-title" @close="payment = null" @cancel="preventPendingClose">
      <form v-if="payment" class="rep-payment" @submit.prevent="savePayment">
        <div class="rep-heading"><div><h2 id="payment-title">Record payment</h2><p>{{ payment.invoice }}</p></div><button type="button" :disabled="busy || !!pending" aria-label="Close payment" @click="paymentDialog.close()">×</button></div>
        <p v-if="paymentError" class="rep-error" role="alert">{{ paymentError }}</p>
        <p>Outstanding <strong>{{ money(payment.outstanding, payment.currency) }}</strong></p>
        <p v-if="!payment.modes.length">No payment modes have a matching company cash or bank account. <a :href="desk('Sales Invoice', payment.invoice)">Open in ERPNext</a></p>
        <fieldset v-else :disabled="busy || !!pending">
          <label>Amount ({{ payment.currency }}) <input v-model.number="payment.amount" type="number" min="0.000001" :max="payment.outstanding" step="any" required></label>
          <label>Mode of payment<select v-model="payment.mode" required><option value="">Select a mode</option><option v-for="mode in payment.modes" :key="mode.name">{{ mode.name }}</option></select></label>
          <label>Transaction reference <input v-model="payment.reference" maxlength="140" :required="referenceRequired"></label>
          <button class="rep-primary" type="submit">Submit payment</button>
        </fieldset>
        <button v-if="pending && !busy" class="rep-primary" type="button" @click="sendPending">Retry payment request</button>
      </form>
    </dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { call, ApiError } from '../api'
import Icon from '../components/Icon.vue'

const route = useRoute()
const router = useRouter()
const page = computed(() => route.meta.repPage || 'catalog')
const pageTitle = computed(() => ({ quotations: 'Quotations', invoices: 'Invoices', activity: 'Activity' })[page.value])
const documentType = computed(() => page.value === 'invoices' ? 'Sales Invoice' : 'Quotation')
const setup = ref(null)
const profileName = ref('')
const profile = computed(() => setup.value?.profiles.find(row => row.name === profileName.value))
const access = (type, action) => !!setup.value?.documents[type]?.[action]
const canSell = computed(() => access('quotation', 'post') || access('invoice', 'post'))
const scope = (params = {}) => ({ pos_profile: profileName.value, ...params })
const commands = {
  post_document: (args, options) => call('esafe_salesrep.api.sales_rep.post_document', args, options),
  record_payment: (args, options) => call('esafe_salesrep.api.sales_rep.record_payment', args, options),
  check_in: (args, options) => call('esafe_salesrep.api.sales_rep.check_in', args, options),
}

const error = ref('')
const notice = ref('')
const loading = ref(false)
const busy = ref(false)
const pending = ref(null)
const query = ref('')
const brand = ref('')
const group = ref('')
const filters = ref({ brand: [], item_group: [] })
const catalog = ref({ items: [] })
const brokenImages = ref(new Set())
const photo = ref(null)
const photoDialog = ref(null)
const orderPanel = ref(null)
const kind = ref('quotation')
const customerSearch = ref('')
const customer = ref(null)
const matches = ref([])
const customerSearched = ref(false)
const lines = ref([])
const discount = ref(0)
const documentDate = ref('')
const note = ref('')
const passcode = ref('')
const reviewing = ref(false)
const estimate = ref(null)
const documentSearch = ref('')
const soldItem = ref('')
const soldBrand = ref('')
const dueOnly = ref(false)
const team = ref(false)
const records = ref([])
const recordsMore = ref(false)
const checkingIn = ref(false)
const payment = ref(null)
const paymentDialog = ref(null)
const paymentError = ref('')
const referenceRequired = computed(() => payment.value?.modes.find(mode => mode.name === payment.value.mode)?.reference_required)
const readyToReview = computed(() => !!customer.value && !!lines.value.length &&
  lines.value.every(line => Number.isFinite(line.qty) && line.qty >= 0.000001) &&
  Number(discount.value) >= 0 && Number(discount.value) <= 100 && !reviewing.value && !checkingIn.value)
const overLimit = computed(() => setup.value?.discount_limit > 0 && Number(discount.value) > setup.value.discount_limit)
const needsDeskApproval = computed(() => overLimit.value && setup.value.discount_approval === 'Request only')
const requiresPasscode = computed(() => overLimit.value && !needsDeskApproval.value)

let requestVersion = 0
let searchTimer
let customerTimer
let active = true

function money(amount, currency) {
  if (!currency || amount == null) return '—'
  return new Intl.NumberFormat(undefined, { style: 'currency', currency, currencyDisplay: 'code' }).format(amount)
}
function desk(doctype, name) {
  return '/app/' + doctype.toLowerCase().replaceAll(' ', '-') + '/' + encodeURIComponent(name)
}
function printLink(doctype, name) {
  return '/printview?' + new URLSearchParams({ doctype, name })
}
function coordinate(value) {
  return Number(value).toFixed(5)
}
function openPhoto(item) {
  photo.value = item
  photoDialog.value.showModal()
}
function add(item) {
  const existing = lines.value.find(line => line.name === item.name)
  if (existing) existing.qty = (Number(existing.qty) || 0) + 1
  else if (lines.value.length < 100) lines.value.push({ name: item.name, item_name: item.item_name, uom: item.uom, qty: 1 })
  else error.value = 'A sale can contain up to 100 different items.'
}
function pickCustomer(row) {
  customer.value = row
  customerSearch.value = row.customer_name
  matches.value = []
}
function salePayload() {
  return {
    customer: customer.value?.name,
    items: lines.value.map(line => ({ item_code: line.name, qty: line.qty })),
    discount: Number(discount.value),
    document_date: documentDate.value || null,
    note: note.value,
  }
}

async function loadSetup() {
  error.value = ''
  try {
    setup.value = await call('esafe_salesrep.api.sales_rep.bootstrap')
    kind.value = access('quotation', 'post') ? 'quotation' : 'invoice'
    profileName.value = setup.value.profiles[0]?.name || ''
  } catch (e) {
    error.value = e.message
  }
}

async function loadPage(more = false) {
  const version = ++requestVersion
  loading.value = true
  try {
    if (page.value === 'catalog') {
      const result = await call('esafe_salesrep.api.sales_rep.catalog', scope({
        search: query.value, brand: brand.value, item_group: group.value,
        customer: customer.value?.name, start: more ? catalog.value.items.length : 0,
      }))
      if (version !== requestVersion) return
      if (more) result.items = [...catalog.value.items, ...result.items]
      catalog.value = result
    } else {
      const start = more ? records.value.length : 0
      const result = page.value === 'activity'
        ? await call('esafe_salesrep.api.sales_rep.list_activity', scope({ team: Number(team.value), start }))
        : await call('esafe_salesrep.api.sales_rep.list_documents', scope({
          kind: page.value === 'invoices' ? 'invoice' : 'quotation',
          search: documentSearch.value, due_only: Number(dueOnly.value), start,
          item_code: soldItem.value, brand: soldBrand.value, team: Number(team.value),
        }))
      if (version !== requestVersion) return
      records.value = more ? [...records.value, ...result.rows] : result.rows
      recordsMore.value = result.more
    }
  } catch (e) {
    if (version === requestVersion) error.value = e.message
  } finally {
    if (version === requestVersion) loading.value = false
  }
}

watch(profileName, async name => {
  if (!name) return
  customer.value = null
  customerSearch.value = ''
  brand.value = ''
  group.value = ''
  soldBrand.value = ''
  filters.value = { brand: [], item_group: [] }
  try {
    const result = await call('esafe_salesrep.api.sales_rep.catalog_filters', scope())
    if (name === profileName.value) filters.value = result
  } catch (e) {
    if (name === profileName.value) error.value = e.message
  }
})

watch([profileName, page, query, brand, group, customer, documentSearch, soldItem, soldBrand, dueOnly, team], () => {
  clearTimeout(searchTimer)
  requestVersion += 1
  if (!profile.value) return
  loading.value = true
  error.value = ''
  records.value = []
  recordsMore.value = false
  catalog.value = { items: [] }
  searchTimer = setTimeout(loadPage, 180)
})

watch([customerSearch, profileName], ([search, name]) => {
  clearTimeout(customerTimer)
  matches.value = []
  customerSearched.value = false
  if (!name || customer.value || search.trim().length < 2) return
  customerTimer = setTimeout(async () => {
    try {
      const result = await call('esafe_salesrep.api.sales_rep.customers', scope({ search }))
      if (name === profileName.value && search === customerSearch.value && !customer.value) {
        matches.value = result
        customerSearched.value = true
      }
    } catch (e) {
      if (name === profileName.value && search === customerSearch.value) error.value = e.message
    }
  }, 220)
})

watch([lines, discount, customer, note, documentDate, kind], () => {
  estimate.value = null
}, { deep: true })
watch(kind, () => { documentDate.value = ''; passcode.value = '' })

async function review() {
  reviewing.value = true
  error.value = ''
  const payload = salePayload()
  const target = kind.value
  try {
    const result = await call('esafe_salesrep.api.sales_rep.preview', scope({ kind: target, payload }))
    if (target === kind.value && JSON.stringify(payload) === JSON.stringify(salePayload())) estimate.value = result
  } catch (e) {
    error.value = e.message
  } finally {
    reviewing.value = false
  }
}

function requestKey() {
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')
  return [hex.slice(0, 8), hex.slice(8, 12), hex.slice(12, 16), hex.slice(16, 20), hex.slice(20)].join('-')
}
function submit(method, params) {
  if (pending.value || busy.value) return
  pending.value = { method, args: scope({ ...params, request_key: requestKey() }) }
  return sendPending()
}

async function sendPending() {
  if (busy.value || !pending.value) return
  const { method, args } = pending.value
  busy.value = true
  error.value = ''
  paymentError.value = ''
  notice.value = ''
  try {
    const result = await commands[method](args, { timeout: 25000 })
    if (!result) throw new Error('ERPNext did not return a confirmation.')
    pending.value = null
    if (method === 'post_document') {
      lines.value = []
      discount.value = 0
      note.value = ''
      passcode.value = ''
      documentDate.value = ''
      customer.value = null
      customerSearch.value = ''
      const isInvoice = args.kind === 'invoice'
      notice.value = (isInvoice ? 'Invoice ' : 'Quotation ') + result.name + ' submitted.'
      const target = isInvoice ? '/invoices' : '/quotations'
      if (route.path === target) loadPage()
      else await router.push(target)
    } else if (method === 'record_payment') {
      notice.value = 'Payment ' + result.name + ' recorded.'
      paymentDialog.value.close()
      loadPage()
    } else {
      notice.value = 'Check-in recorded at ' + result.creation?.slice(0, 19) + ' (server time).'
      loadPage()
    }
  } catch (e) {
    if (e instanceof ApiError && (e.rejected || (e.status >= 400 && e.status < 500 && e.status !== 408))) {
      pending.value = null
      if (method === 'post_document') estimate.value = null
    }
    const message = pending.value ? 'The request result could not be confirmed.' : e.message
    if (method === 'record_payment') paymentError.value = message
    else error.value = message
  } finally {
    busy.value = false
  }
}

function saveSale() {
  submit('post_document', {
    kind: kind.value,
    payload: { ...salePayload(), reviewed_total: estimate.value.total, reviewed_currency: estimate.value.currency },
    passcode: passcode.value || undefined,
  })
}
async function openPayment(row) {
  busy.value = true
  error.value = ''
  try {
    const result = await call('esafe_salesrep.api.sales_rep.payment_options', scope({ invoice: row.name }))
    paymentError.value = ''
    payment.value = { ...result, invoice: row.name, amount: result.outstanding, mode: result.modes[0]?.name || '', reference: '' }
    paymentDialog.value.showModal()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
function preventPendingClose(event) {
  if (pending.value || busy.value) event.preventDefault()
}
function savePayment() {
  const { invoice, mode, amount, reference } = payment.value
  submit('record_payment', { invoice, mode, amount, reference })
}
function checkIn() {
  if (!navigator.geolocation) {
    error.value = 'Location is unavailable. Open the workspace over HTTPS in a browser with location access.'
    return
  }
  error.value = ''
  checkingIn.value = true
  navigator.geolocation.getCurrentPosition(({ coords }) => {
    checkingIn.value = false
    if (active) submit('check_in', { latitude: coords.latitude, longitude: coords.longitude, accuracy: coords.accuracy })
  }, () => {
    checkingIn.value = false
    error.value = 'Location was unavailable. Check browser location permission and try again.'
  }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 })
}

onMounted(loadSetup)
onUnmounted(() => {
  active = false
  clearTimeout(searchTimer)
  clearTimeout(customerTimer)
})
</script>

<style src="./sales-rep.css"></style>
