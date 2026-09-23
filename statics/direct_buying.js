(() => {
  const form = document.getElementById('direct-buying-form');
  if (!form) return;
  const preview = document.getElementById('order-preview');
  function update() {
    const groups = new Map();
    for (const input of form.querySelectorAll('input[name="product_id"]')) {
      const id = input.value;
      const qty = Number(form.elements['quantity_' + id].value);
      const option = form.elements['offer_' + id]?.selectedOptions[0];
      if (!Number.isInteger(qty) || qty <= 0 || !option) continue;
      const key = option.dataset.supplier + ' · ' + option.dataset.currency;
      groups.set(key, (groups.get(key) || 0) + qty * Number(option.dataset.price));
    }
    preview.replaceChildren();
    if (!groups.size) { preview.textContent = 'Selecciona cajas y proveedor'; return; }
    for (const [key, cents] of groups) {
      const line = document.createElement('span');
      const [supplier, currency] = key.split(' · ');
      line.textContent = `${supplier}: ${currency} ${(cents / 100).toFixed(2)}`;
      preview.append(line);
    }
  }
  form.addEventListener('change', update);
  form.addEventListener('input', update);
  form.addEventListener('submit', event => {
    const quantities = [...form.querySelectorAll('.order-qty')].map(x => Number(x.value));
    const currencies = new Set([...form.querySelectorAll('input[name="product_id"]')].map((input, index) =>
      quantities[index] > 0 ? form.elements['offer_' + input.value]?.selectedOptions[0]?.dataset.currency : null
    ).filter(Boolean));
    if (!quantities.some(x => x > 0) || currencies.size > 1) {
      event.preventDefault();
      alert(currencies.size > 1 ? 'Prepara por separado las compras en USD y MXN.' : 'Selecciona al menos una caja con precio vigente.');
    }
  });
  update();
})();
