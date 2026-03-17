import React, { useEffect, useRef } from 'react';
import { createChart, ColorType } from 'lightweight-charts';

export const CandlestickChart = ({ data, colors: {
    backgroundColor = 'transparent',
    textColor = '#9ca3af',
} = {}, timeframe = '1d' }) => {
    const chartContainerRef = useRef();
    const chartRef = useRef(null);

    useEffect(() => {
        if (!data || data.length === 0) return;
        if (!chartContainerRef.current) return;

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
                    mode: 1,
                }
            });
        } catch (error) {
            console.error('Chart init error:', error);
            return;
        }

        chartRef.current = chart;

        const seriesOptions = {
            upColor: '#22c55e',
            downColor: '#ef4444',
            borderVisible: false,
            wickUpColor: '#22c55e',
            wickDownColor: '#ef4444',
        };
        const candlestickSeries = chart.addCandlestickSeries(seriesOptions);

        try {
            // Preserve full timestamps for intraday candles while still filtering invalid points.
            const dataMap = new Map();
            for (let i = 0; i < data.length; i++) {
                const item = data[i];
                if (
                    isNaN(item.open) || item.open === null ||
                    isNaN(item.high) || item.high === null ||
                    isNaN(item.low) || item.low === null ||
                    isNaN(item.close) || item.close === null ||
                    !item.time
                ) continue;

                const dateParsed = new Date(item.time);
                if (isNaN(dateParsed.getTime())) continue;

                const normalizedTime = timeframe === '1d'
                    ? dateParsed.toISOString().split('T')[0]
                    : Math.floor(dateParsed.getTime() / 1000);
                dataMap.set(normalizedTime, {
                    time: normalizedTime,
                    open: Number(item.open),
                    high: Number(item.high),
                    low: Number(item.low),
                    close: Number(item.close),
                });
            }

            const safeData = Array.from(dataMap.values());
            safeData.sort((a, b) => {
                const aValue = typeof a.time === 'number' ? a.time : new Date(a.time).getTime();
                const bValue = typeof b.time === 'number' ? b.time : new Date(b.time).getTime();
                return aValue - bValue;
            });

            if (safeData.length > 0) {
                candlestickSeries.setData(safeData);
                chart.timeScale().fitContent();
            }
        } catch (error) {
            console.error('Candle chart render error:', error);
        }

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            if (chartRef.current) {
                chartRef.current.remove();
                chartRef.current = null;
            }
        };
    }, [data, backgroundColor, textColor, timeframe]);

    return (
        <div ref={chartContainerRef} className="w-full h-full relative z-20" />
    );
};
