<template>
  <div class="proactive-section" v-if="loaded">
    <div class="section-header" @click="expanded = !expanded">
      <span class="section-title">{{ $t("proactive.title") }}</span>
      <i :class="expanded ? 'el-icon-arrow-up' : 'el-icon-arrow-down'"></i>
    </div>

    <div class="section-body" v-show="expanded">
      <!-- 总开关 -->
      <div class="form-row">
        <span class="row-label">{{ $t("proactive.enabled") }}</span>
        <el-switch v-model="config.enabled"></el-switch>
      </div>

      <template v-if="config.enabled">
        <!-- 星期几 -->
        <div class="form-row">
          <span class="row-label">{{ $t("proactive.weekdays") }}</span>
          <el-checkbox-group v-model="config.weekdays">
            <el-checkbox v-for="d in weekdayOptions" :key="d.value" :label="d.value">
              {{ d.label }}
            </el-checkbox>
          </el-checkbox-group>
          <span class="hint">{{ $t("proactive.weekdaysHint") }}</span>
        </div>

        <!-- 提问时段 -->
        <div class="form-row">
          <span class="row-label">{{ $t("proactive.timeWindow") }}</span>
          <el-select v-model="startHour" :disabled="!config.enabled" class="time-select">
            <el-option v-for="h in hourOptions" :key="h" :label="h" :value="h"></el-option>
          </el-select>
          <span class="time-colon">:</span>
          <el-select v-model="startMinute" class="time-select">
            <el-option v-for="m in minuteOptions" :key="m" :label="m" :value="m"></el-option>
          </el-select>
          <span class="time-sep">{{ $t("proactive.to") }}</span>
          <el-select v-model="endHour" class="time-select">
            <el-option v-for="h in hourOptions" :key="h" :label="h" :value="h"></el-option>
          </el-select>
          <span class="time-colon">:</span>
          <el-select v-model="endMinute" class="time-select">
            <el-option v-for="m in minuteOptions" :key="m" :label="m" :value="m"></el-option>
          </el-select>
        </div>

        <!-- 提问间隔 -->
        <div class="form-row">
          <span class="row-label">{{ $t("proactive.interval") }}</span>
          <el-select v-model="config.interval" class="interval-select">
            <el-option
              v-for="opt in intervalOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value">
            </el-option>
          </el-select>
        </div>

        <!-- 固定台词 -->
        <div class="form-row column">
          <span class="row-label">
            {{ $t("proactive.script") }}
            <span class="required">*</span>
          </span>
          <el-input
            type="textarea"
            :rows="2"
            maxlength="100"
            show-word-limit
            v-model="config.script"
            :placeholder="$t('proactive.scriptPlaceholder')">
          </el-input>
        </div>

        <div class="notice">{{ $t("proactive.reconnectNotice") }}</div>
      </template>
    </div>
  </div>
</template>

<script>
export default {
  name: "ProactiveConfigCard",
  props: {
    // 父组件传入：后端返回的已有配置（null 表示从未配置过）
    proactiveConfig: {
      type: Object,
      default: null,
    },
  },
  data() {
    return {
      loaded: false,
      expanded: false, // 默认折叠
      // 组件内部维护的表单状态（init 时从 props 初始化一次）
      config: {
        enabled: false,
        weekdays: [],
        interval: 900,
        script: "",
      },
      startHour: "00",
      startMinute: "00",
      endHour: "23",
      endMinute: "45",
    };
  },
  computed: {
    // 生成 00-23 小时选项
    hourOptions() {
      return Array.from({ length: 24 }, (_, i) => String(i).padStart(2, "0"));
    },
    // 生成 00/15/30/45 分钟档位
    minuteOptions() {
      return ["00", "15", "30", "45"];
    },
    // 间隔档位（分钟 → 秒）
    intervalOptions() {
      const mins = [5, 10, 15, 20, 30, 45, 60];
      return mins.map((m) => ({
        value: m * 60,
        label: this.$t("proactive.minutes", { n: m }),
      }));
    },
    // 星期选项：值与 Python isoweekday 对齐（1=周一 7=周日）
    weekdayOptions() {
      return [
        { value: 1, label: this.$t("proactive.mon") },
        { value: 2, label: this.$t("proactive.tue") },
        { value: 3, label: this.$t("proactive.wed") },
        { value: 4, label: this.$t("proactive.thu") },
        { value: 5, label: this.$t("proactive.fri") },
        { value: 6, label: this.$t("proactive.sat") },
        { value: 7, label: this.$t("proactive.sun") },
      ];
    },
  },
  watch: {
    // 父组件异步加载完成后，proactiveConfig 从 null 变为对象——此时初始化表单
    proactiveConfig: {
      handler(val) {
        this.initForm(val);
      },
      immediate: true,
    },
  },
  methods: {
    initForm(serverConfig) {
      // 无论有没有历史配置，都先标记 loaded 让区块显示
      this.loaded = true;
      if (!serverConfig || typeof serverConfig !== "object") {
        return; // 从未配置：保持默认值
      }
      this.config.enabled = !!serverConfig.enabled;
      this.config.script = serverConfig.script || "";
      this.config.interval = Number(serverConfig.interval) || 900;
      if (Array.isArray(serverConfig.weekdays)) {
        this.config.weekdays = serverConfig.weekdays.map(Number);
      }
      // "HH:MM" 拆成两个下拉的值；分钟不在 15 档位上时取最近档
      if (typeof serverConfig.start_time === "string") {
        const [h, m] = serverConfig.start_time.split(":");
        this.startHour = String(h || "00").padStart(2, "0");
        this.startMinute = this.nearestMinute(m);
      }
      if (typeof serverConfig.end_time === "string") {
        const [h, m] = serverConfig.end_time.split(":");
        this.endHour = String(h || "23").padStart(2, "0");
        this.endMinute = this.nearestMinute(m);
      }
    },
    nearestMinute(m) {
      const n = Number(m) || 0;
      const opts = [0, 15, 30, 45];
      const nearest = opts.reduce((a, b) => (Math.abs(b - n) < Math.abs(a - n) ? b : a));
      return String(nearest).padStart(2, "0");
    },
    // 供父组件保存时调用：校验并导出配置对象；校验失败返回 null
    exportConfig() {
      if (!this.config.enabled) {
        // 关闭状态：只存开关，其他字段一并存回（保留用户上次输入，便于再开）
        return {
          enabled: false,
          start_time: `${this.startHour}:${this.startMinute}`,
          end_time: `${this.endHour}:${this.endMinute}`,
          interval: this.config.interval,
          script: this.config.script,
          weekdays: this.config.weekdays,
        };
      }
      // 开启状态：台词必填校验
      if (!this.config.script || !this.config.script.trim()) {
        this.$message.error(this.$t("proactive.scriptRequired"));
        return null;
      }
      return {
        enabled: true,
        start_time: `${this.startHour}:${this.startMinute}`,
        end_time: `${this.endHour}:${this.endMinute}`,
        interval: this.config.interval,
        script: this.config.script.trim(),
        weekdays: this.config.weekdays,
      };
    },
  },
};
</script>

<style scoped>
.proactive-section {
  margin-top: 24px;
  border-top: 1px solid #ebeef5;
  padding-top: 16px;
}
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  user-select: none;
}
.section-title {
  font-size: 15px;
  font-weight: 600;
}
.section-body {
  padding: 16px 8px 4px;
}
.form-row {
  display: flex;
  align-items: center;
  margin-bottom: 14px;
  flex-wrap: wrap;
  gap: 6px;
}
.form-row.column {
  flex-direction: column;
  align-items: flex-start;
}
.row-label {
  min-width: 90px;
  font-size: 14px;
}
.required {
  color: #f56c6c;
}
.time-select {
  width: 76px;
}
.time-colon,
.time-sep {
  margin: 0 2px;
}
.interval-select {
  width: 120px;
}
.hint {
  width: 100%;
  font-size: 12px;
  color: #909399;
  margin-left: 96px;
}
.notice {
  font-size: 12px;
  color: #e6a23c;
  margin-top: 4px;
}
</style>
