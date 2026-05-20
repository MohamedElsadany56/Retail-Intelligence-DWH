const state = {
  catalog: [],
  departments: [],
  cart: new Map(),
  activeDepartment: "ALL",
  search: "",
  recommendations: [],
  orders: [],
};

const $ = (id) => document.getElementById(id);

function money(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(Number(value || 0));
}

function number(value) {
  return new Intl.NumberFormat("en-US").format(Number(value || 0));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function drawIcons() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Request failed");
  }
  return payload;
}

function showToast(message, isError = false) {
  const toast = $("toast");
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("show"), 3200);
}

function cartEntries() {
  return Array.from(state.cart.values());
}

function cartSubtotal() {
  return cartEntries().reduce((total, row) => total + row.item.price * row.quantity, 0);
}

function cartQuantity() {
  return cartEntries().reduce((total, row) => total + row.quantity, 0);
}

function filteredCatalog() {
  const query = state.search.trim().toLowerCase();
  return state.catalog.filter((item) => {
    const matchesDepartment =
      state.activeDepartment === "ALL" || item.department === state.activeDepartment;
    const matchesSearch =
      !query ||
      item.name.toLowerCase().includes(query) ||
      item.product_type.toLowerCase().includes(query);
    return matchesDepartment && matchesSearch;
  });
}

function renderDepartments() {
  const total = state.departments.reduce((sum, department) => sum + department.count, 0);
  const rows = [{ name: "ALL", count: total }, ...state.departments];
  $("departmentList").innerHTML = rows
    .map((department) => {
      const label = department.name === "ALL" ? "All" : department.name;
      const active = department.name === state.activeDepartment ? "active" : "";
      return `
        <button class="department-button ${active}" type="button" data-department="${escapeHtml(department.name)}">
          <span>${escapeHtml(label)}</span>
          <span>${number(department.count)}</span>
        </button>
      `;
    })
    .join("");
}

function renderProducts() {
  const items = filteredCatalog();
  $("catalogCount").textContent = `${number(items.length)} products available`;
  $("activeDepartment").textContent =
    state.activeDepartment === "ALL" ? "All" : state.activeDepartment;

  if (!items.length) {
    $("productGrid").innerHTML = `<div class="empty-state">No matching products</div>`;
    return;
  }

  $("productGrid").innerHTML = items
    .map(
      (item) => `
        <article class="product-card">
          <div class="product-image" style="background-image: url('${escapeHtml(item.image_url)}')">
            <span class="department-tag">${escapeHtml(item.department)}</span>
          </div>
          <div class="product-body">
            <div>
              <h3 class="product-name">${escapeHtml(item.name)}</h3>
              <div class="product-meta">${escapeHtml(item.product_type)} · ${number(item.basket_count)} baskets</div>
            </div>
            <div class="product-bottom">
              <span class="price">${money(item.price)}</span>
              <button class="add-button" type="button" data-add="${escapeHtml(item.id)}" aria-label="Add ${escapeHtml(item.name)}">
                <i data-lucide="plus"></i>
              </button>
            </div>
          </div>
        </article>
      `,
    )
    .join("");
  drawIcons();
}

function renderCart() {
  const entries = cartEntries();
  const subtotal = cartSubtotal();
  const quantity = cartQuantity();

  $("cartChipCount").textContent = quantity;
  $("metricItems").textContent = number(quantity);
  $("metricSubtotal").textContent = money(subtotal);
  $("cartSubtotal").textContent = money(subtotal);
  $("checkoutTotal").textContent = money(subtotal);
  $("checkoutBtn").disabled = entries.length === 0;

  if (!entries.length) {
    $("cartItems").innerHTML = `<div class="empty-state">Cart is empty</div>`;
    drawIcons();
    return;
  }

  $("cartItems").innerHTML = entries
    .map(
      ({ item, quantity }) => `
        <div class="cart-line">
          <div>
            <span class="line-title">${escapeHtml(item.name)}</span>
            <div class="line-sub">${money(item.price)} · ${money(item.price * quantity)}</div>
          </div>
          <div class="qty-control" aria-label="Quantity controls">
            <button class="qty-button" type="button" data-dec="${escapeHtml(item.id)}" aria-label="Decrease ${escapeHtml(item.name)}">
              <i data-lucide="minus"></i>
            </button>
            <span class="qty-value">${quantity}</span>
            <button class="qty-button" type="button" data-inc="${escapeHtml(item.id)}" aria-label="Increase ${escapeHtml(item.name)}">
              <i data-lucide="plus"></i>
            </button>
          </div>
        </div>
      `,
    )
    .join("");
  drawIcons();
}

function recommendationMetric(recommendations) {
  const best = recommendations.reduce(
    (max, item) => Math.max(max, Number(item.confidence || 0)),
    0,
  );
  return `${Math.round(best * 100)}%`;
}

function renderRecommendations(payload) {
  state.recommendations = payload.recommendations || [];
  $("metricMatch").textContent = recommendationMetric(state.recommendations);
  $("recBadge").textContent = state.cart.size ? "Rules" : "Popular";

  if (!state.recommendations.length) {
    $("recommendationList").innerHTML = `<div class="empty-state">No basket matches yet</div>`;
    drawIcons();
    return;
  }

  $("recommendationList").innerHTML = state.recommendations
    .map((item) => {
      const confidence = item.confidence ? `${Math.round(item.confidence * 100)}%` : "Popular";
      const lift = item.lift ? `${Number(item.lift).toFixed(1)}x lift` : `${number(item.basket_count)} baskets`;
      return `
        <div class="rec-line">
          <div>
            <span class="rec-title">${escapeHtml(item.name)}</span>
            <div class="rec-reason">${escapeHtml(item.reason)}</div>
            <div class="rec-score">
              <span>${confidence}</span>
              <span>${lift}</span>
            </div>
          </div>
          <button class="rec-add" type="button" data-add="${escapeHtml(item.id)}" aria-label="Add ${escapeHtml(item.name)}">
            <i data-lucide="plus"></i>
          </button>
        </div>
      `;
    })
    .join("");
  drawIcons();
}

function renderOrders() {
  $("metricOrders").textContent = number(state.orders.length);
  if (!state.orders.length) {
    $("recentOrders").innerHTML = `<div class="empty-state">No completed orders</div>`;
    return;
  }

  $("recentOrders").innerHTML = state.orders
    .map(
      (order) => `
        <div class="recent-order">
          <span class="order-id">${escapeHtml(order.id)}</span>
          <div class="order-meta">
            <span>${number(order.item_count)} items</span>
            <strong>${money(order.total)}</strong>
          </div>
        </div>
      `,
    )
    .join("");
}

function addToCart(itemId, amount = 1) {
  const item = state.catalog.find((candidate) => candidate.id === itemId);
  if (!item) return;

  const existing = state.cart.get(itemId);
  state.cart.set(itemId, {
    item,
    quantity: Math.min(99, (existing?.quantity || 0) + amount),
  });
  renderCart();
  loadRecommendations();
}

function changeQuantity(itemId, amount) {
  const existing = state.cart.get(itemId);
  if (!existing) return;

  const nextQuantity = existing.quantity + amount;
  if (nextQuantity <= 0) {
    state.cart.delete(itemId);
  } else {
    state.cart.set(itemId, { ...existing, quantity: Math.min(99, nextQuantity) });
  }
  renderCart();
  loadRecommendations();
}

function clearCart() {
  state.cart.clear();
  renderCart();
  loadRecommendations();
}

async function loadHealth() {
  const payload = await api("/api/health");
  const summary = payload.summary;
  $("dataSource").textContent = `${number(summary.basket_count)} baskets · ${number(summary.rule_count)} rules`;
}

async function loadCatalog() {
  const payload = await api("/api/catalog?limit=500");
  state.catalog = payload.items || [];
  renderProducts();
}

async function loadDepartments() {
  const payload = await api("/api/departments");
  state.departments = payload.departments || [];
  renderDepartments();
}

async function loadOrders() {
  const payload = await api("/api/orders?limit=8");
  state.orders = payload.orders || [];
  renderOrders();
}

async function loadRecommendations() {
  try {
    const payload = await api("/api/recommendations", {
      method: "POST",
      body: JSON.stringify({
        items: Array.from(state.cart.keys()),
        limit: 8,
      }),
    });
    renderRecommendations(payload);
  } catch (error) {
    showToast(error.message, true);
  }
}

function openCheckout() {
  if (!state.cart.size) return;
  $("checkoutModal").classList.add("open");
  $("checkoutModal").setAttribute("aria-hidden", "false");
}

function closeCheckout() {
  $("checkoutModal").classList.remove("open");
  $("checkoutModal").setAttribute("aria-hidden", "true");
}

async function submitOrder(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const formData = new FormData(form);
  const customer = Object.fromEntries(formData.entries());
  const items = cartEntries().map(({ item, quantity }) => ({
    item_id: item.id,
    quantity,
  }));

  try {
    const payload = await api("/api/orders", {
      method: "POST",
      body: JSON.stringify({ customer, items }),
    });
    showToast(`${payload.order.id} completed · ${money(payload.order.total)}`);
    form.reset();
    closeCheckout();
    clearCart();
    await loadOrders();
  } catch (error) {
    showToast(error.message, true);
  }
}

function bindEvents() {
  $("departmentList").addEventListener("click", (event) => {
    const button = event.target.closest("[data-department]");
    if (!button) return;
    state.activeDepartment = button.dataset.department;
    renderDepartments();
    renderProducts();
  });

  $("productGrid").addEventListener("click", (event) => {
    const button = event.target.closest("[data-add]");
    if (!button) return;
    addToCart(button.dataset.add);
  });

  $("recommendationList").addEventListener("click", (event) => {
    const button = event.target.closest("[data-add]");
    if (!button) return;
    addToCart(button.dataset.add);
  });

  $("cartItems").addEventListener("click", (event) => {
    const increment = event.target.closest("[data-inc]");
    const decrement = event.target.closest("[data-dec]");
    if (increment) changeQuantity(increment.dataset.inc, 1);
    if (decrement) changeQuantity(decrement.dataset.dec, -1);
  });

  $("searchInput").addEventListener("input", (event) => {
    state.search = event.target.value;
    renderProducts();
  });

  $("clearCartBtn").addEventListener("click", clearCart);
  $("checkoutBtn").addEventListener("click", openCheckout);
  $("closeModalBtn").addEventListener("click", closeCheckout);
  $("checkoutForm").addEventListener("submit", submitOrder);
  $("refreshBtn").addEventListener("click", refresh);
  $("cartJump").addEventListener("click", () => $("cartPanel").scrollIntoView({ behavior: "smooth" }));
  $("checkoutModal").addEventListener("click", (event) => {
    if (event.target.id === "checkoutModal") closeCheckout();
  });
}

async function refresh() {
  try {
    await Promise.all([loadHealth(), loadCatalog(), loadDepartments(), loadOrders()]);
    renderCart();
    await loadRecommendations();
    drawIcons();
  } catch (error) {
    showToast(error.message, true);
  }
}

bindEvents();
refresh();
