import { createApp } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import "element-plus/dist/index.css";
import App from "./App.vue";
import "./style.css";
window.studioMessage = ElMessage;
window.studioConfirm = (message, title = "请确认") =>
  ElMessageBox.confirm(message, title, {
    confirmButtonText: "确认",
    cancelButtonText: "取消",
    type: "warning",
  });
createApp(App).mount("#app");
