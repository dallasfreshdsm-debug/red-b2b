(() => {
  const form = document.getElementById('direct-buying-form');
  if (!form) return;
  const cells = [...document.querySelectorAll('.df-product-cell')];
  const preview = document.getElementById('order-preview');
  const cart = document.getElementById('df-cart-lines');
  function update() {
    cart.replaceChildren();
    preview.replaceChildren();
    const groups = new Map();
    let selected = 0;
    for (const cell of cells) {
      const input = cell.querySelector('.order-qty');
      const qty = Number(input.value);
      const select = cell.querySelector('.order-offer');
      const option = select.selectedOptions[0];
      if (!Number.isInteger(qty) || qty <= 0) continue;
      selected++;
      const row = document.createElement('div');
      row.className = 'df-cart-line';
      const details = document.createElement('span');
      const title = document.createElement('strong'); title.textContent = cell.dataset.name;
      const sub = document.createElement('small');
      sub.textContent = `${qty} ${cell.dataset.unit} · ${option?.dataset.supplier || 'Sin proveedor vigente'}`;
      details.append(title, sub);
      const edit = document.createElement('button'); edit.type = 'button'; edit.className = 'df-cart-edit'; edit.textContent = 'Modificar';
      edit.addEventListener('click', () => { cell.scrollIntoView({behavior: 'smooth', block: 'center'}); input.focus(); });
      row.append(details, edit); cart.append(row);
      if (option?.dataset.supplier) {
        const key = `${option.dataset.supplier} · ${option.dataset.currency}`;
        groups.set(key, (groups.get(key) || 0) + qty * Number(option.dataset.price));
      }
      const price = cell.querySelector('.df-cell-price');
      price.textContent = option?.dataset.supplier ?
        `${option.dataset.currency} ${(Number(option.dataset.price) / 100).toFixed(2)}` : 'Por cotizar';
    }
    if (!selected) cart.innerHTML = '<p class="empty">Tu orden está vacía.</p>';
    if (!groups.size) { preview.textContent = selected ? 'Faltan precios vigentes' : 'Selecciona productos'; return; }
    for (const [key, cents] of groups) {
      const line = document.createElement('span');
      const [supplier, currency] = key.split(' · ');
      line.textContent = `${supplier}: ${currency} ${(cents / 100).toFixed(2)}`;
      preview.append(line);
    }
  }
  function add(id, qty) {
    const cell = cells.find(c => c.dataset.id === id);
    if (!cell) return;
    const input = cell.querySelector('.order-qty');
    input.value = String(Math.min(100000, Number(input.value || 0) + qty));
    update();
  }
  cells.forEach(cell => {
    cell.querySelectorAll('[data-change]').forEach(button => button.addEventListener('click', () => {
      const input = cell.querySelector('.order-qty');
      input.value = String(Math.max(0, Math.min(100000, Number(input.value || 0) + Number(button.dataset.change))));
      update();
    }));
    cell.querySelector('.order-qty').addEventListener('input', update);
    cell.querySelector('.order-offer').addEventListener('change', update);
  });
  document.querySelectorAll('.guide-add').forEach(button => button.addEventListener('click', () => add(button.dataset.id, Number(button.dataset.qty))));
  const catalogSearch = document.getElementById('catalog-search');
  catalogSearch.addEventListener('input', () => {
    const query = catalogSearch.value.trim().toLocaleLowerCase();
    cells.forEach(cell => { cell.hidden = Boolean(query && !cell.dataset.search.includes(query)); });
  });
  const cartSearch = document.getElementById('cart-search');
  cartSearch.addEventListener('input', () => {
    const query = cartSearch.value.trim().toLocaleLowerCase();
    const results = document.getElementById('cart-search-results');
    results.replaceChildren();
    if (!query) return;
    for (const cell of cells.filter(c => c.dataset.search.includes(query)).slice(0, 8)) {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'quick-result';
      button.textContent = `${cell.dataset.name} · ${cell.dataset.unit}`;
      button.addEventListener('click', () => { add(cell.dataset.id, 1); cartSearch.value = ''; results.replaceChildren(); });
      results.append(button);
    }
    if (!results.children.length) results.textContent = 'No se encontró el producto. Puedes agregarlo en Configurar productos.';
  });
  form.addEventListener('submit', event => {
    const picked = cells.filter(cell => Number(cell.querySelector('.order-qty').value) > 0);
    const currencies = new Set(picked.map(cell => cell.querySelector('.order-offer').selectedOptions[0]?.dataset.currency).filter(Boolean));
    if (!picked.length || picked.length > 50 || picked.some(cell => !cell.querySelector('.order-offer').value) || currencies.size > 1) {
      event.preventDefault();
      alert(!picked.length ? 'Selecciona al menos una caja.' : currencies.size > 1 ?
        'Prepara por separado las compras en USD y MXN.' : 'Revisa los productos sin proveedor/precio vigente; máximo 50 por orden.');
      return;
    }
    // Omit zero-quantity rows so a large synchronized catalog fits the request.
    cells.filter(cell => !picked.includes(cell)).forEach(cell => cell.querySelectorAll('input,select').forEach(field => { field.disabled = true; }));
  });
  update();
})();
