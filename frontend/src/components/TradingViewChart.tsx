/**
 * TradingViewChart — embeds TradingView's free Advanced Chart widget via iframe.
 *
 * Why iframe instead of lightweight-charts npm package:
 *   The full TradingView widget provides volume bars, drawing tools, indicators,
 *   and live data for free — no API key required. The npm package requires
 *   self-supplied OHLCV data, which would need a separate data pipeline.
 *
 * Symbol mapping:
 *   TSLA    → "NASDAQ:TSLA"
 *   BTC-USD → "COINBASE:BTCUSD"
 *   Others  → "NASDAQ:{ticker}" (fallback)
 */

import { useMemo } from "react"

const SYMBOL_MAP: Record<string, string> = {
  TSLA: "NASDAQ:TSLA",
  "BTC-USD": "COINBASE:BTCUSD",
}

interface TradingViewChartProps {
  ticker: string
  height?: number
}

export function TradingViewChart({ ticker, height = 360 }: TradingViewChartProps) {
  const tvSymbol = SYMBOL_MAP[ticker] ?? `NASDAQ:${ticker}`

  const src = useMemo(() => {
    const params = new URLSearchParams({
      symbol: tvSymbol,
      interval: "1",
      theme: "dark",
      style: "1",
      locale: "en",
      toolbar_bg: "#0f1117",
      enable_publishing: "false",
      hide_side_toolbar: "false",
      allow_symbol_change: "false",
      save_image: "false",
      hide_top_toolbar: "false",
    })
    return `https://www.tradingview.com/widgetembed/?${params.toString()}`
  }, [tvSymbol])

  return (
    <div className="w-full rounded-lg border border-surface-border overflow-hidden bg-surface-card">
      <iframe
        src={src}
        style={{ width: "100%", height }}
        frameBorder={0}
        allowTransparency
        scrolling="no"
        title={`TradingView chart — ${ticker}`}
        loading="lazy"
      />
    </div>
  )
}
