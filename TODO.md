# TODO / 規劃

> 這個檔案放在公開的 repo 中，內容保持在規劃層級即可。

## 網站架構（規劃中）

| 位址 | 內容 | 狀態 |
|---|---|---|
| `aegisulf.com/` | 單頁、極簡的分流首頁：音樂區 / 軟體區 / 個人介紹 | **未做** |
| `aegisulf.com/music` | 音樂專區，也就是目前網站的內容 | 目前仍在根目錄；**首頁完成前先不搬** |
| `aegisulf.com/lycanzip` | 另一個專案，不在這裡開發，但檔案會放在這個 repo | 之後 |

`aegisulf.github.io` 已自動轉到 `aegisulf.com`（`CNAME`）。網站的正式網址、sitemap、分享連結、統計網域都已改為 `aegisulf.com`。

## 待辦

### 1. 新首頁（分流頁）
- [ ] 釐清下方「待釐清」的項目
- [ ] 設計：版面、風格、中英文
- [ ] 實作：`src/templates/landing.html`，由 `tools/build.py` 產生
- [ ] 檢查：一屏、手機、語言自動偵測、分享預覽圖、Umami 事件

### 2. 現行網站搬到 `/music`（首頁完成後才做）
- [ ] `tools/build.py` 加入「基底路徑」，目前所有內部連結都是 `/en/...`、`/zh/...`
- [ ] 舊網址導向：`/en/releases/...`、`/zh/releases/...` 等放置轉址頁到新位置
- [ ] 更新 canonical、hreflang、sitemap、分享網址、結構化資料
- [ ] 語言自動導向的路徑、404 導回的位置、`style.css` / `pages.css` / 圖片路徑
- [ ] Search Console：新增網址前綴的資源並重新提交 sitemap
- [ ] 外部連結：Spotify / X / Bandcamp 等簡介裡的網址要不要改成 `/music`

### 3. `/lycanzip`
- [ ] 決定放置方式（資料夾名稱、是否有自己的建置）
- [ ] 確保 `tools/build.py` 不會刪除或覆寫它（目前只會清除 `en/`、`zh/`）
- [ ] 要不要列入 sitemap

### 4. 其他
- [ ] 10/16 之後：Graveforged 在 11/6 上架，補上 Spotify / Apple Music 網址
- [ ] Bandcamp 上架 Scarred Slumber 後補連結
- [ ] 作品故事、第一篇 blog 文章
- [ ] Search Console / Umami 網站設定改用 `aegisulf.com`

## 待釐清（新首頁）

1. 三個入口的內容：
   - **音樂區**：導向 `/music`。
   - **軟體區**：是只有 `lycanzip` 一個，還是會有多個專案？是導向一個列表頁，還是直接放連結？
   - **個人介紹**：是首頁內的一個區塊，還是獨立頁面（例如 `/about`）？要寫哪些內容？
2. 視覺風格：沿用現在的狼人插圖與紅色風格，還是比較中性的新設計（因為它要涵蓋音樂與軟體）？
3. 語言：同樣中英文自動偵測嗎？
4. 到 `aegisulf.com` 的訪客，是看到分流頁（需要多點一次進入音樂），還是仍以音樂為主？
5. 統計：整個網域共用同一個 Umami 網站，還是各區分開？
6. 對外的定位與名稱：`aegisulf.com` 的頁面標題、說明文字、分享預覽圖要用什麼？
