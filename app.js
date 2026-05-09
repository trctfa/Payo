const form = document.getElementById("analysis-form");
const sampleBtn = document.getElementById("sample-btn");
const resultEmpty = document.getElementById("result-empty");
const resultBox = document.getElementById("result");

const output = {
  state: document.getElementById("state"),
  meaning: document.getElementById("meaning"),
  scenarios: document.getElementById("scenarios"),
  risks: document.getElementById("risks"),
  actions: document.getElementById("actions"),
};

const chart = document.getElementById("chart");
const ctx = chart.getContext("2d");
let lastRows = [];
let lastPrice = null;

function parseRows(raw) {
  return raw
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [open, high, low, close, volume] = line.split(",").map((v) => Number(v.trim()));
      if ([open, high, low, close].some((v) => Number.isNaN(v) || v <= 0)) {
        throw new Error(`資料格式錯誤：${line}`);
      }
      return { open, high, low, close, volume: Number.isNaN(volume) ? 0 : volume };
    });
}

function average(values) {
  if (!values.length) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function movingAverage(closes, window) {
  if (closes.length < window) return null;
  return average(closes.slice(-window));
}

function calcRsi(closes, period = 14) {
  if (closes.length <= period) return null;
  let gains = 0;
  let losses = 0;

  for (let i = closes.length - period; i < closes.length; i += 1) {
    const diff = closes[i] - closes[i - 1];
    if (diff >= 0) gains += diff;
    else losses += Math.abs(diff);
  }

  if (losses === 0) return 100;
  const rs = gains / losses;
  return 100 - 100 / (1 + rs);
}

function getTrend(price, ma5, ma20) {
  if (!ma5 || !ma20) return "資料不足";
  if (price > ma5 && ma5 > ma20) return "偏多";
  if (price < ma5 && ma5 < ma20) return "偏空";
  return "盤整";
}

function getSupportResistance(rows) {
  const recent = rows.slice(-20);
  const support = Math.min(...recent.map((row) => row.low));
  const resistance = Math.max(...recent.map((row) => row.high));
  return { support, resistance };
}

function distancePercent(price, target) {
  return ((price - target) / target) * 100;
}

function confidenceScore({ trend, rsi, price, support, resistance }) {
  let score = 50;
  if (trend === "偏多") score += 20;
  if (trend === "偏空") score -= 20;
  if (rsi !== null && rsi > 55 && rsi < 75) score += 10;
  if (rsi !== null && rsi < 45 && rsi > 25) score -= 10;

  const pos = (price - support) / Math.max(resistance - support, 1e-6);
  if (pos >= 0.45 && pos <= 0.7) score += 10;
  if (pos > 0.9 || pos < 0.1) score -= 5;

  if (score >= 70) return "高";
  if (score >= 45) return "中";
  return "低";
}

function analyze(input) {
  const closes = input.rows.map((row) => row.close);
  const ma5 = movingAverage(closes, 5);
  const ma20 = movingAverage(closes, 20);
  const rsi = calcRsi(closes);
  const trend = getTrend(input.price, ma5, ma20);
  const { support, resistance } = getSupportResistance(input.rows);

  const nearSupport = distancePercent(input.price, support);
  const nearResistance = distancePercent(input.price, resistance);
  const signalLevel = confidenceScore({
    trend,
    rsi,
    price: input.price,
    support,
    resistance,
  });

  const state = `${input.market} ${input.symbol}（${input.timeframe}）目前結構為「${trend}」，訊號一致性為 ${signalLevel}。`;

  let meaning = `目前價格 ${input.price.toFixed(2)}，20 根區間支撐約 ${support.toFixed(
    2
  )}、壓力約 ${resistance.toFixed(2)}。`;

  if (nearResistance > -1.5 && nearResistance < 0) {
    meaning += " 價格正在壓力位下方測壓，若無量突破容易拉回。";
  } else if (nearSupport > 0 && nearSupport < 1.5) {
    meaning += " 價格靠近支撐區，若守住有機會出現技術反彈。";
  } else if (input.price > resistance) {
    meaning += " 價格已突破近 20 根壓力，需觀察是否站穩與量能續強。";
  } else if (input.price < support) {
    meaning += " 價格跌破近 20 根支撐，代表短線結構轉弱。";
  } else {
    meaning += " 價格位於區間中段，建議等待方向更明確。";
  }

  if (ma5 && ma20) {
    meaning += ` 均線參考：MA5=${ma5.toFixed(2)}，MA20=${ma20.toFixed(2)}。`;
  }
  if (rsi !== null) {
    meaning += ` RSI14=${rsi.toFixed(1)}。`;
  }

  const scenarios = [];
  if (input.price >= resistance * 0.995) {
    scenarios.push("若放量突破壓力並連續兩根 K 收在其上方，可視為趨勢延續訊號。");
    scenarios.push("若突破但量能不足，常見假突破後回測壓力轉支撐失敗。");
  } else if (input.price <= support * 1.005) {
    scenarios.push("若支撐守住且短線量增，可能出現跌深反彈。");
    scenarios.push("若有效跌破支撐且反彈無力，可能展開下一段下跌。");
  } else {
    scenarios.push("目前偏區間整理，突破壓力或跌破支撐前以觀察為主。");
    scenarios.push("若後續出現帶量長紅/長黑，方向訊號會更明確。");
  }

  const risks = [
    `關鍵風險位：${support.toFixed(2)}（跌破可能轉弱）`,
    `關鍵壓力位：${resistance.toFixed(2)}（未突破前容易震盪）`,
    "單一指標容易失真，請搭配事件風險（財報、法說會、總體數據）。",
  ];

  const actions = [
    `依你的「${input.style}」偏好，先定義失效點與風險報酬比（至少 1:1.5）。`,
    "把分析流程固定化：趨勢（MA）→結構（支撐壓力）→動能（RSI）→量能驗證。",
    "若要優化程式，可加入多時間框架一致性（日線 + 1H）加權評分。",
    "下一版可加入回測與到價提醒，讓分析結果可追蹤與驗證。",
  ];

  if (input.notes.trim()) {
    actions.push(`你提供的補充資訊重點：${input.notes.trim()}`);
  }

  return {
    state,
    meaning,
    scenarios,
    risks,
    actions,
  };
}

function drawChart(rows, currentPrice) {
  const rect = chart.getBoundingClientRect();
  const width = rect.width;
  const height = rect.height;
  ctx.clearRect(0, 0, width, height);

  const padding = { top: 20, right: 20, bottom: 28, left: 20 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  const highs = rows.map((row) => row.high);
  const lows = rows.map((row) => row.low);
  const max = Math.max(...highs, currentPrice);
  const min = Math.min(...lows, currentPrice);
  const range = Math.max(max - min, 1e-6);

  const candleWidth = Math.max(chartWidth / rows.length - 4, 2);
  const step = chartWidth / rows.length;

  ctx.strokeStyle = "#cbd5e1";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(padding.left, padding.top + chartHeight);
  ctx.lineTo(width - padding.right, padding.top + chartHeight);
  ctx.stroke();

  rows.forEach((row, i) => {
    const x = padding.left + i * step + step / 2;
    const yHigh = padding.top + ((max - row.high) / range) * chartHeight;
    const yLow = padding.top + ((max - row.low) / range) * chartHeight;
    const yOpen = padding.top + ((max - row.open) / range) * chartHeight;
    const yClose = padding.top + ((max - row.close) / range) * chartHeight;
    const up = row.close >= row.open;

    ctx.strokeStyle = up ? "#16a34a" : "#dc2626";
    ctx.fillStyle = up ? "#22c55e" : "#ef4444";

    ctx.beginPath();
    ctx.moveTo(x, yHigh);
    ctx.lineTo(x, yLow);
    ctx.stroke();

    const bodyY = Math.min(yOpen, yClose);
    const bodyH = Math.max(Math.abs(yOpen - yClose), 2);
    ctx.fillRect(x - candleWidth / 2, bodyY, candleWidth, bodyH);
  });

  const yPrice = padding.top + ((max - currentPrice) / range) * chartHeight;
  ctx.strokeStyle = "#1d4ed8";
  ctx.setLineDash([5, 4]);
  ctx.beginPath();
  ctx.moveTo(padding.left, yPrice);
  ctx.lineTo(width - padding.right, yPrice);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.fillStyle = "#1d4ed8";
  ctx.font = "14px sans-serif";
  ctx.fillText(`現價 ${currentPrice.toFixed(2)}`, padding.left + 8, Math.max(yPrice - 6, 16));
}

function resizeCanvas() {
  const ratio = window.devicePixelRatio || 1;
  const rect = chart.getBoundingClientRect();
  chart.width = Math.max(Math.floor(rect.width * ratio), 320);
  chart.height = Math.floor(260 * ratio);
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

  if (lastRows.length && lastPrice !== null) {
    drawChart(lastRows, lastPrice);
  }
}

function renderList(target, items) {
  target.innerHTML = "";
  items.forEach((text) => {
    const li = document.createElement("li");
    li.textContent = text;
    target.appendChild(li);
  });
}

function runAnalysis() {
  const symbol = document.getElementById("symbol").value.trim();
  const market = document.getElementById("market").value;
  const price = Number(document.getElementById("price").value);
  const timeframe = document.getElementById("timeframe").value;
  const style = document.getElementById("style").value;
  const notes = document.getElementById("notes").value;
  const rawData = document.getElementById("kline-data").value.trim();

  if (!symbol || Number.isNaN(price) || price <= 0) {
    alert("請先填寫股票代碼與有效股價。");
    return;
  }

  let rows = [];
  try {
    rows = parseRows(rawData);
  } catch (error) {
    alert(error.message);
    return;
  }

  if (rows.length < 20) {
    alert("建議至少輸入 20 根 K，分析會比較穩定。");
    return;
  }

  const report = analyze({
    symbol,
    market,
    price,
    timeframe,
    style,
    notes,
    rows,
  });

  output.state.textContent = report.state;
  output.meaning.textContent = report.meaning;
  renderList(output.scenarios, report.scenarios);
  renderList(output.risks, report.risks);
  renderList(output.actions, report.actions);

  resultEmpty.classList.add("hidden");
  resultBox.classList.remove("hidden");

  lastRows = rows.slice(-60);
  lastPrice = price;
  drawChart(lastRows, lastPrice);
}

sampleBtn.addEventListener("click", () => {
  const symbol = document.getElementById("symbol");
  const price = document.getElementById("price");
  const notes = document.getElementById("notes");
  const data = document.getElementById("kline-data");

  symbol.value = "2330";
  price.value = "955";
  notes.value = "近期 AI 題材帶動成交量放大，市場關注法說會展望。";
  data.value = [
    "930,938,925,935,21500",
    "935,941,931,940,20100",
    "940,946,936,944,18800",
    "944,950,939,948,22100",
    "948,952,943,945,19800",
    "945,951,941,949,20500",
    "949,954,946,952,23200",
    "952,958,949,957,25400",
    "957,960,952,955,21600",
    "955,959,951,953,19500",
    "953,956,949,950,18400",
    "950,955,947,952,17700",
    "952,958,950,956,20600",
    "956,962,953,960,24300",
    "960,965,957,963,25100",
    "963,968,959,961,23900",
    "961,966,958,964,22800",
    "964,970,962,968,26300",
    "968,973,964,969,27100",
    "969,972,965,967,24700",
    "967,971,963,965,23600",
    "965,969,960,962,22500",
    "962,966,958,960,21400",
    "960,964,956,959,20300",
    "959,963,955,957,19800",
  ].join("\n");
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  runAnalysis();
});

window.addEventListener("resize", resizeCanvas);
resizeCanvas();
