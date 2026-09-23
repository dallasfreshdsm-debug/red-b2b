(() => {
  'use strict';
  const form = document.getElementById('buying-form');
  if (!form) return;
  const cart = [];
  const byId = (id) => document.getElementById(id);
  const key = (item) => [item.product.toLocaleLowerCase(), item.unit.toLocaleLowerCase(), item.spec.toLocaleLowerCase()].join('\u0000');
  const message = (text) => { byId('buying-message').textContent = text; };
  const make = (tag, className, text) => {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  };
  function add(product, unit, spec = '', quantity = 1) {
    product = String(product || '').trim(); unit = String(unit || '').trim(); spec = String(spec || '').trim();
    const qty = Number(quantity);
    if (!product || !unit || product.length > 160 || unit.length > 30 || spec.length > 500 || !Number.isFinite(qty) || qty <= 0) {
      message('Escribe un producto, unidad y cantidad válidos.'); return;
    }
    const incoming = {product, unit, spec, quantity: qty};
    const current = cart.find(x => key(x) === key(incoming));
    if (current) current.quantity += qty;
    else if (cart.length < 8) cart.push(incoming);
    else { message('Cada solicitud admite hasta 8 productos.'); return; }
    byId('quick-product-search').value = '';
    byId('quick-results').replaceChildren();
    message(product + ' agregado a mi compra.');
    render();
  }
  function render() {
    const container = byId('cart-lines');
    container.replaceChildren();
    byId('cart-count').textContent = cart.length + (cart.length === 1 ? ' producto' : ' productos');
    if (!cart.length) { container.append(make('p', 'empty', 'Tu lista de compra está vacía.')); return; }
    cart.forEach((item, index) => {
      const row = make('div', 'purchase-line');
      const info = make('div', 'purchase-line-info');
      info.append(make('strong', '', item.product), make('small', '', item.unit + (item.spec ? ' · ' + item.spec : '')));
      const controls = make('div', 'purchase-qty');
      const minus = make('button', 'qtybtn', '−'); minus.type = 'button'; minus.setAttribute('aria-label', 'Restar ' + item.product);
      minus.addEventListener('click', () => { item.quantity = Math.max(0, item.quantity - 1); if (!item.quantity) cart.splice(index, 1); render(); });
      const qty = make('input', 'qty'); qty.type = 'number'; qty.min = '0.001'; qty.step = 'any'; qty.value = String(item.quantity); qty.setAttribute('aria-label', 'Cantidad de ' + item.product);
      qty.addEventListener('change', () => { const n = Number(qty.value); if (!Number.isFinite(n) || n <= 0) { message('La cantidad debe ser mayor que cero.'); qty.value = String(item.quantity); return; } item.quantity = n; render(); });
      const plus = make('button', 'qtybtn', '+'); plus.type = 'button'; plus.setAttribute('aria-label', 'Sumar ' + item.product);
      plus.addEventListener('click', () => { item.quantity += 1; render(); });
      const remove = make('button', 'remove-line', 'Quitar'); remove.type = 'button'; remove.setAttribute('aria-label', 'Quitar ' + item.product);
      remove.addEventListener('click', () => { cart.splice(index, 1); render(); });
      controls.append(minus, qty, plus, remove); row.append(info, controls); container.append(row);
    });
  }
  function quickResults() {
    const q = byId('quick-product-search').value.trim().toLocaleLowerCase();
    const results = byId('quick-results'); results.replaceChildren();
    if (!q) return;
    const matches = [...document.querySelectorAll('.catalog-add')].filter(button =>
      (button.dataset.product + ' ' + button.dataset.spec + ' ' + button.dataset.unit).toLocaleLowerCase().includes(q)
    ).slice(0, 7);
    matches.forEach(button => {
      const row = make('button', 'quick-result', button.dataset.product + ' · ' + button.dataset.unit);
      row.type = 'button'; row.addEventListener('click', () => add(button.dataset.product, button.dataset.unit, button.dataset.spec));
      results.append(row);
    });
    if (!matches.length) results.append(make('p', 'muted', 'Sin coincidencias. Agrégalo como producto nuevo abajo.'));
  }
  byId('quick-product-search').addEventListener('input', quickResults);
  byId('product-search').addEventListener('input', (event) => {
    const q = event.target.value.trim().toLocaleLowerCase();
    document.querySelectorAll('.product-cell').forEach(cell => { cell.hidden = Boolean(q && !cell.dataset.search.includes(q)); });
  });
  document.querySelectorAll('.catalog-add,.guide-add').forEach(button => button.addEventListener('click', () =>
    add(button.dataset.product, button.dataset.unit, button.dataset.spec, button.dataset.quantity || 1)
  ));
  byId('add-product').addEventListener('click', () => {
    const product = byId('new-product-name'); const unit = byId('new-product-unit'); const spec = byId('new-product-spec');
    if (!product.value.trim() || !unit.value.trim()) { message('Escribe el nombre del producto y la unidad.'); product.focus(); return; }
    add(product.value, unit.value, spec.value); product.value = ''; unit.value = ''; spec.value = ''; product.focus();
  });
  form.addEventListener('submit', (event) => {
    if (!cart.length) { event.preventDefault(); message('Agrega por lo menos un producto antes de solicitar cotizaciones.'); return; }
    const fields = byId('cart-fields'); fields.replaceChildren();
    for (const item of cart) for (const [name, value] of Object.entries({item_product: item.product, item_unit: item.unit, item_specification: item.spec, item_quantity: String(item.quantity)})) {
      const hidden = make('input'); hidden.type = 'hidden'; hidden.name = name; hidden.value = value; fields.append(hidden);
    }
  });
  render();
})();
