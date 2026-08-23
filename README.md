# Personal Weather

以 `uv` 管理的個人命令列天氣工具。可輸入中文或英文地名；省略地名時，會根據目前公開 IP 位址推測城市。

```powershell
uv run weather 台北
uv run weather "New York" --lang en
uv run weather
```

資料來源為 [Open-Meteo](https://open-meteo.com/) 的地理編碼與天氣 API；當它無法辨識中文地名時，會以 OpenStreetMap 的 Nominatim 作為地理編碼備援。IP 位置由 ipapi.co 提供。IP 定位僅為大致位置，使用 VPN、行動網路或公司網路時尤其可能不準確。

中文地名若在台灣與其他地區同名，工具會優先採用台灣的行政區或聚落結果（例如「基隆」、「桃園」）；店家等興趣點不會作為查詢結果。

## 選項

- `LOCATION`：中文或英文地名（可省略）
- `--lang {zh-TW,en}`：輸出語言，預設 `zh-TW`
- `--version`：顯示版本
