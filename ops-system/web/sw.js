/* Service worker: иконка на экране и работа при пропавшей связи.
 *
 * Что кэшируем: только саму страницу и её обвязку. Данные — никогда:
 * чек-лист про то, что на точке СЕЙЧАС, и показать вчерашнюю картину
 * хуже, чем честно сказать «связи нет».
 *
 * Версия в имени кэша меняется вместе со сборкой страницы — иначе телефон
 * будет держать старую версию до полной переустановки.
 */
const CACHE = 'romashka-v07.09';
const SHELL = ['/', '/manifest.json'];

self.addEventListener('install', e => {
  // Новая версия не ждёт, пока закроются старые вкладки: смена работает
  // с одного экрана, и «обновится потом» здесь означает «не обновится».
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).catch(() => {}));
});

self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    for(const k of await caches.keys()){
      if(k !== CACHE) await caches.delete(k);
    }
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  // Запросы к серверу мимо кэша всегда: явка, отметки, фото и проверки
  // должны идти вживую или честно падать.
  if(e.request.method !== 'GET' || url.pathname.startsWith('/api/')) return;
  // Страницу берём из сети, а кэш — запасной аэродром на случай, когда
  // связи нет. Так человек всегда получает свежую версию, если она есть.
  e.respondWith((async () => {
    try{
      const res = await fetch(e.request);
      if(res && res.ok && url.origin === self.location.origin){
        const c = await caches.open(CACHE);
        c.put(e.request, res.clone());
      }
      return res;
    }catch(err){
      const hit = await caches.match(e.request);
      if(hit) return hit;
      if(e.request.mode === 'navigate'){
        const page = await caches.match('/');
        if(page) return page;
      }
      throw err;
    }
  })());
});
