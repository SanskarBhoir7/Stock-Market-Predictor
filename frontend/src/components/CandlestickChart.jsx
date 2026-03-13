import React, { useEffect, useRef } from 'react';
import { createChart, ColorType, CandlestickSeries } from 'lightweight-charts';

export const CandlestickChart = ({ data, colors: {
    backgroundColor = 'transparent',
    textColor = '#9ca3af',
} = {} }) => {
    const chartContainerRef = useRef();
    const chartRef = useRef(null);

    useEffect(() => {
        if (!data || data.length === 0) return;
        
        // Setup chart instances
        const handleResize = () => {
            if (chartRef.current && chartContainerRef.current) {
               chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
            }
        };

        let chart;
        try {
            chart = createChart(chartContainerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: backgroundColor },
                textColor,
            },
            width: chartContainerRef.current.clientWidth || 600,
            height: 400,
            grid: {
                vertLines: { color: 'rgba(192, 132, 252, 0.1)' },
                horzLines: { color: 'rgba(192, 132, 252, 0.1)' },
            },
            rightPriceScale: {
                borderVisible: false,
            },
            timeScale: {
                borderVisible: false,
                timeVisible: true,
                secondsVisible: false,
            },
            crosshair: {
                mode: 1, // CrosshairMode.Normal - but passing integer enum 1 avoids importing mode type from lightweight-charts
            }
            });
        } catch (error) {
            console.error("Chart init error:", error);
            return;
        }
        
        chartRef.current = chart;

        // Lightweight Charts v5 uses addSeries(); older versions use addCandlestickSeries().
        let candlestickSeries;
        const seriesOptions = {
            upColor: '#22c55e',
            downColor: '#ef4444',
            borderVisible: false,
            wickUpColor: '#22c55e',
            wickDownColor: '#ef4444',
        };
        if (typeof chart.addCandlestickSeries === 'function') {
            candlestickSeries = chart.addCandlestickSeries(seriesOptions);
        } else if (typeof chart.addSeries === 'function') {
            candlestickSeries = chart.addSeries(CandlestickSeries, seriesOptions);
        } else {
            console.error("Chart series API unavailable.");
            chart.remove();
            chartRef.current = null;
            return;
        }

        // Lightweight Charts crash heavily on duplicated/unsynchronized date indices. Safety set:
        try {
            const uniqueTimestamps = new Set();
            const safeData = [];
            for (let i = 0; i < data.length; i++) {
                 const item = data[i];
                 // Validate OHLC are valid numbers, else LightweightCharts will crash
                 if (
                     isNaN(item.open) || item.open === null ||
                     isNaN(item.high) || item.high === null ||
                     isNaN(item.low) || item.low === null ||
                     isNaN(item.close) || item.close === null
                 ) continue;
                 
                 // Generate numeric unix timestamp (seconds) for absolute Chronological safety
                 const timeSec = Math.floor(new Date(item.time).getTime() / 1000);
                 
                 if (!uniqueTimestamps.has(timeSec)) {
                     uniqueTimestamps.add(timeSec);
                     safeData.push({
                         ...item,
                         time: timeSec
                     });
                 }
            }
            // Sort ascending strictly mathematically
            safeData.sort((a, b) => a.time - b.time);
            candlestickSeries.setData(safeData);
            chart.timeScale().fitContent();
        } catch (error) {
            console.error("Candle chart render error:", error);
        }

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            if (chartRef.current) {
                chartRef.current.remove();
                chartRef.current = null;
            }
        };
    }, [data, backgroundColor, textColor]);

    return (
        <div ref={chartContainerRef} className="w-full h-full relative z-20" />
    );
};
