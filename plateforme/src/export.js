export function portfolioCsv(portfolio) {
  const cell = value => {
    const text = typeof value === 'string' && /^[\s\uFEFF]*[=+@-]/.test(value) ? `'${value}` : String(value);
    return `"${text.replace(/"/g, '""')}"`;
  };
  return '\uFEFF' + ['Symbole;Nom;Catégorie;Poids (%);Nature', ...portfolio.positions.map(position => [position.symbol, position.name, position.category, position.weight, portfolio.isDemo ? 'Illustration non personnalisée' : 'Simulation du moteur'].map(cell).join(';'))].join('\r\n');
}

// Une réponse réseau ne doit jamais réapparaître après une remise à zéro du profil.
export function createRequestGuard() {
  let revision = 0;
  let controller = null;
  return {
    begin() { controller?.abort(); controller = new AbortController(); return { revision, signal: controller.signal }; },
    invalidate() { revision++; controller?.abort(); controller = null; },
    isCurrent(request) { return request.revision === revision && !request.signal.aborted; },
  };
}

export function boundedChatPayload(input, maximumBytes = 60 * 1024) {
  const payload = { ...input, conversation: [...input.conversation] };
  const bytes = value => new TextEncoder().encode(JSON.stringify(value)).byteLength;
  while (payload.conversation.length && bytes(payload) > maximumBytes) payload.conversation.shift();
  if (bytes(payload) > maximumBytes) throw new Error('Le contexte est trop volumineux. Réduisez la longueur de votre message.');
  return payload;
}
