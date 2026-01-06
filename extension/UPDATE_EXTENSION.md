# ⚡ Обновите расширение Chrome

## Быстрая перезагрузка (30 секунд)

1. Откройте новую вкладку
2. Введите в адресной строке: `chrome://extensions/`
3. Найдите **"Audio Tab Recorder"**
4. Нажмите кнопку **⟳ (обновить)**
5. Готово!

## Что было исправлено?

✅ Добавлена поддержка Manifest V3 через Offscreen Document API
✅ Исправлена ошибка: `Cannot read properties of undefined (reading 'getUserMedia')`
✅ Расширение теперь полностью совместимо с современным Chrome

## Проверка

После перезагрузки:

1. Откройте вкладку с аудио (YouTube, Spotify)
2. Кликните на иконку расширения
3. Нажмите **"Start Recording"**
4. ✅ **Должно работать!**

Записи доступны на: http://localhost:8000

---

Если что-то не работает, откройте консоль расширения (chrome://extensions/ → Details → Inspect views: service worker) и проверьте логи.
