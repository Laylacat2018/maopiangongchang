<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from "vue";
import * as echarts from "echarts/core";
import { LineChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  MarkAreaComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
echarts.use([
  LineChart,
  GridComponent,
  TooltipComponent,
  MarkAreaComponent,
  CanvasRenderer,
]);
const props = defineProps({ points: Array, shots: Array });
const el = ref();
let chart;
function draw() {
  if (!chart) return;
  const pts = [...(props.points || [])].sort(
    (a, b) => a.data.second - b.data.second,
  );
  chart.setOption(
    {
      grid: { left: 42, right: 20, top: 25, bottom: 30 },
      tooltip: {
        trigger: "axis",
        valueFormatter: (v) => (Number(v) * 100).toFixed(1) + "%",
      },
      xAxis: { type: "value", axisLabel: { formatter: "{value}s" } },
      yAxis: {
        min: 0,
        max: 1,
        type: "value",
        axisLabel: { formatter: (v) => v * 100 + "%" },
        splitLine: { lineStyle: { color: "#edf1ee" } },
      },
      series: [
        {
          type: "line",
          data: pts.map((x) => [x.data.second, x.data.ratio]),
          smooth: false,
          symbolSize: 7,
          lineStyle: { color: "#25875c", width: 3 },
          itemStyle: { color: "#25875c" },
          areaStyle: { color: "#d4efdf" },
          markArea: {
            silent: true,
            itemStyle: { color: "rgba(229,157,107,.08)" },
            label: { fontSize: 10, color: "#647169" },
            data: (props.shots || []).map((x) => [
              { name: x.name, xAxis: x.start },
              { xAxis: x.end },
            ]),
          },
        },
      ],
    },
    true,
  );
}
watch(() => [props.points, props.shots], draw, { deep: true });
const resize = () => chart?.resize();
onMounted(() => {
  chart = echarts.init(el.value);
  draw();
  window.addEventListener("resize", resize);
});
onBeforeUnmount(() => {
  chart?.dispose();
  window.removeEventListener("resize", resize);
});
</script>
<template>
  <div
    ref="el"
    class="chart"
    role="img"
    aria-label="观众留存与镜头时间对照曲线"
  ></div>
</template>
