// frontend/static/js/mock.js
// 统一的 Mock 数据生成与接口模拟

const MockData = {
    // 模拟储罐当前状态
    getTankStatus: function() {
        // 随机生成一个液位，用来模拟不同区间的状态
        const V = 500;
        const L = Math.random() * V; // 0 - 500 之间
        const ratio = L / V;
        
        let status = 'NORMAL';
        let k = 1.0;
        
        if (ratio >= 0.95) {
            status = 'EMERGENCY';
            k = 0;
        } else if (ratio >= 0.9) {
            status = 'ALERT';
            k = 0;
        } else if (ratio >= 0.8) {
            status = 'WARNING';
            // 计算弹性系数 k (示例公式)
            k = 1 - ((L - 0.8 * V) / (0.1 * V)) * (1 - 0.3);
        }

        return {
            level: L.toFixed(2),
            ratio: (ratio * 100).toFixed(1),
            status: status,
            k: k.toFixed(2),
            timestamp: new Date().toLocaleTimeString()
        };
    },

    // 模拟本周期各车间建议速率
    getScheduleResults: function(status, k) {
        const workshops = [
            { id: 'WS001', name: '预处理车间', max: 12 },
            { id: 'WS002', name: '合成车间一', max: 15 },
            { id: 'WS003', name: '合成车间二', max: 15 },
            { id: 'WS004', name: '精馏车间', max: 10 },
            { id: 'WS005', name: '包装车间', max: 8 },
            { id: 'WS006', name: '清洗车间', max: 20 },
            { id: 'WS007', name: '辅助车间', max: 10 }
        ];

        const T = 0.5; // 0.5 小时

        let totalRate = 0;
        let results = [];

        workshops.forEach(ws => {
            let rate = 0;
            if (status === 'NORMAL') {
                 // 正常情况下，假设根据处理能力和容量，平均分配（这里简化为最大值的一半加些随机）
                 rate = (ws.max * 0.6) * (0.8 + Math.random()*0.4); 
            } else if (status === 'WARNING') {
                 rate = (ws.max * k) * (0.8 + Math.random()*0.4);
            } else {
                 // ALERT 和 EMERGENCY 均为 0
                 rate = 0;
            }
            
            // 确保不超过最大值
            rate = Math.min(rate, ws.max);

            const vol = rate * T;
            totalRate += rate;

            results.push({
                workshop_id: ws.id,
                workshop_name: ws.name,
                max_rate: ws.max.toFixed(2),
                allowed_rate: rate.toFixed(2),
                allowed_volume: vol.toFixed(2)
            });
        });

        return {
            total_rate: totalRate.toFixed(2),
            results: results
        };
    },

    // 模拟滚动告警播报数据（最近10条）
    getAlerts: function() {
        const now = new Date();
        const alerts = [];
        const levels = ['ALERT', 'WARNING', 'EMERGENCY', 'WARNING', 'ALERT', 'NORMAL', 'WARNING', 'ALERT', 'EMERGENCY', 'WARNING'];
        const tankLevels = [460, 425, 478, 440, 455, 300, 430, 462, 480, 435];
        const messages = [
            '液位达到告警区间，建议立即停止排放',
            '液位达到预警区间，已启动弹性速率压缩策略',
            '液位达到紧急区间，建议立即停止所有车间排放',
            '液位达到预警区间，已启动弹性速率压缩策略',
            '液位达到告警区间，建议立即停止排放',
            '液位回落至安全区间，恢复正常调度',
            '液位达到预警区间，已启动弹性速率压缩策略',
            '液位达到告警区间，建议立即停止排放',
            '液位达到紧急区间，建议立即停止所有车间排放',
            '液位达到预警区间，已启动弹性速率压缩策略'
        ];
        for (let i = 0; i < 10; i++) {
            const t = new Date(now.getTime() - i * 30 * 60000);
            const mm = t.getMonth() + 1;
            const dd = t.getDate();
            const hh = t.getHours().toString().padStart(2, '0');
            const mi = t.getMinutes().toString().padStart(2, '0');
            const timeStr = mm + '/' + dd + ' ' + hh + ':' + mi;
            const ratio = (tankLevels[i] / 500 * 100).toFixed(1);
            alerts.push({
                time: timeStr,
                level: levels[i],
                msg: messages[i] + '（当前液位' + tankLevels[i].toFixed(2) + 'm³，占比' + ratio + '%）'
            });
        }
        return alerts;
    },

    // 模拟历史趋势数据
    getHistoryTrend: function() {
        let times = [];
        let levels = [];
        let predicted = [];
        
        let now = new Date();
        now.setMinutes(0); // 取整点
        now.setSeconds(0);

        let currentL = 300;
        
        for (let i = 24; i >= 0; i--) {
            let t = new Date(now.getTime() - i * 30 * 60 * 1000); // 每30分钟
            times.push(t.getHours().toString().padStart(2, '0') + ':' + t.getMinutes().toString().padStart(2, '0'));
            
            // 随机波动液位
            currentL = currentL + (Math.random() * 40 - 20); 
            if (currentL > 490) currentL = 490;
            if (currentL < 50) currentL = 50;

            levels.push(currentL.toFixed(1));
            predicted.push((currentL + (Math.random()*10 - 5)).toFixed(1)); // 预测值稍微有一点偏差
        }

        return {
            times: times,
            levels: levels,
            predicted: predicted
        };
    },

    // 生成UUID
    generateUUID: function() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    },

    // 存储历史调度记录，保证数据一致性
    _historyRecordsCache: null,
    
    // 模拟历史调度记录（按调度批次聚合）
    getHistoryScheduleRecords: function() {
        // 如果已缓存，直接返回
        if (this._historyRecordsCache) {
            return this._historyRecordsCache;
        }
        
        const zones = ['NORMAL', 'NORMAL', 'NORMAL', 'WARNING', 'ALERT', 'EMERGENCY'];
        const solverStatuses = ['Optimal', 'Optimal', 'Optimal', 'Infeasible', 'Timeout'];
        let records = [];
        
        for (let i = 0; i < 20; i++) {
            const scheduleTime = new Date(Date.now() - i * 30 * 60000);
            const zone = zones[Math.floor(Math.random() * zones.length)];
            const levelRatio = zone === 'NORMAL' ? 0.5 + Math.random() * 0.3 : 
                              zone === 'WARNING' ? 0.8 + Math.random() * 0.1 :
                              zone === 'ALERT' ? 0.9 + Math.random() * 0.05 : 0.95 + Math.random() * 0.04;
            const tankLevel = 500 * levelRatio;
            const solverStatus = zone === 'ALERT' || zone === 'EMERGENCY' ? 'SKIPPED' : solverStatuses[Math.floor(Math.random() * solverStatuses.length)];
            
            // 模拟告警记录
            let alertInfo = null;
            if (zone === 'ALERT' || zone === 'EMERGENCY' || (zone === 'WARNING' && Math.random() > 0.5)) {
                const alertLevel = zone === 'EMERGENCY' ? 3 : (zone === 'ALERT' ? 2 : 2);
                alertInfo = {
                    alert_level: alertLevel,
                    alert_time: scheduleTime.toLocaleString(),
                    // 消息内容不包含前缀，前端用标签显示级别
                    alert_message: alertLevel === 3 ? 
                        '液位达到紧急区间，建议立即停止所有车间排放（当前液位' + tankLevel.toFixed(2) + 'm³，占比' + (levelRatio*100).toFixed(1) + '%）' : 
                        '液位达到告警区间，建议立即停止排放（当前液位' + tankLevel.toFixed(2) + 'm³，占比' + (levelRatio*100).toFixed(1) + '%）'
                };
            }
            
            records.push({
                schedule_id: this.generateUUID(),
                schedule_time: scheduleTime.toLocaleString(),
                zone: zone,
                tank_level: tankLevel.toFixed(2),
                level_ratio: levelRatio,
                workshop_count: 7,
                solver_status: solverStatus,
                alert_info: alertInfo,
                // 存储完整数据供详情使用
                _detailData: {
                    zone: zone,
                    levelRatio: levelRatio,
                    tankLevel: tankLevel,
                    solverStatus: solverStatus
                }
            });
        }
        
        this._historyRecordsCache = records;
        return records;
    },

    // 根据schedule_id查找历史记录
    findHistoryRecord: function(scheduleId) {
        const records = this.getHistoryScheduleRecords();
        return records.find(r => r.schedule_id === scheduleId);
    },

    // 模拟调度详情数据
    getScheduleDetail: function(scheduleId) {
        // 先查找历史记录，保证数据一致性
        const historyRecord = this.findHistoryRecord(scheduleId);
        
        // 使用历史记录中的数据或重新生成
        let zone, levelRatio, tankLevel, solverStatus;
        if (historyRecord && historyRecord._detailData) {
            zone = historyRecord._detailData.zone;
            levelRatio = historyRecord._detailData.levelRatio;
            tankLevel = historyRecord._detailData.tankLevel;
            solverStatus = historyRecord._detailData.solverStatus;
        } else {
            levelRatio = 0.6 + Math.random() * 0.35;
            zone = levelRatio < 0.8 ? 'NORMAL' : levelRatio < 0.9 ? 'WARNING' : levelRatio < 0.95 ? 'ALERT' : 'EMERGENCY';
            tankLevel = 500 * levelRatio;
            solverStatus = zone === 'ALERT' || zone === 'EMERGENCY' ? 'SKIPPED' : 'Optimal';
        }
        
        const elasticK = zone === 'WARNING' ? 0.5 + Math.random() * 0.4 : null;
        
        // 常量定义
        const V = 500;           // 储罐容量
        const T = 0.5;           // 调度周期(小时)
        const C = 60;            // 处理能力
        const safeRatio = 0.85;  // 安全容量系数
        const bufferRatio = 1.2; // 处理能力缓冲系数
        const minRateRatio = 0.3; // 最低保留比例
        
        // 按PRD公式计算容量约束上限: (V × SAFE_RATIO - L) / T + C
        const capacityLimit = (V * safeRatio - tankLevel) / T + C;
        const processLimit = C * bufferRatio;
        const effectiveLimit = Math.min(capacityLimit, processLimit);

        const inputSnapshot = {
            schedule_id: scheduleId,
            schedule_time: historyRecord ? historyRecord.schedule_time : new Date().toLocaleString(),
            tank_capacity: 500,
            process_capacity: 60,
            schedule_interval_min: 30,
            safe_ratio: 0.85,
            warning_ratio: 0.80,
            alert_ratio: 0.90,
            emergency_ratio: 0.95,
            min_rate_ratio: 0.30,
            process_buffer_ratio: 1.20,
            tank_level: tankLevel,
            level_ratio: levelRatio,
            zone: zone,
            elastic_k: elasticK,
            capacity_limit: capacityLimit,
            process_limit: processLimit,
            effective_limit: effectiveLimit,
            workshop_count: 7
        };

        // 模拟车间配置快照
        const workshops = [
            { id: 'WS001', name: '预处理车间', max: 12, min: 2, weight: 1.0 },
            { id: 'WS002', name: '合成车间一', max: 12, min: 2, weight: 1.0 },
            { id: 'WS003', name: '合成车间二', max: 12, min: 2, weight: 1.0 },
            { id: 'WS004', name: '精馏车间', max: 12, min: 2, weight: 1.0 },
            { id: 'WS005', name: '包装车间', max: 12, min: 2, weight: 1.0 },
            { id: 'WS006', name: '清洗车间', max: 12, min: 2, weight: 1.0 },
            { id: 'WS007', name: '辅助车间', max: 12, min: 2, weight: 1.0 }
        ];

        const workshopSnapshots = workshops.map(ws => ({
            schedule_id: scheduleId,
            workshop_id: ws.id,
            workshop_name: ws.name,
            max_discharge_rate: ws.max,
            min_discharge_rate: ws.min,
            priority_weight: ws.weight,
            elastic_max_rate: zone === 'WARNING' && elasticK ? (ws.max * elasticK).toFixed(2) : null
        }));

        // 模拟建议排放信息
        const suggestions = workshops.map(ws => {
            let allowedRate = 0;
            if (zone === 'NORMAL') {
                allowedRate = ws.max * (0.5 + Math.random() * 0.4);
            } else if (zone === 'WARNING') {
                allowedRate = ws.max * elasticK * (0.5 + Math.random() * 0.4);
            }
            return {
                workshop_id: ws.id,
                workshop_name: ws.name,
                allowed_rate: allowedRate.toFixed(2),
                allowed_volume: (allowedRate * 0.5).toFixed(2),
                schedule_status: zone,
                solver_status: solverStatus
            };
        });

        // 模拟求解过程数据（按PRD 4.3节约束顺序）
        const rMax = 12; // 车间最大排放速率
        const rMin = 2;  // 车间最小排放速率
        
        // 计算弹性上限
        const elasticMaxRate = zone === 'WARNING' && elasticK ? rMax * elasticK : rMax;
        
        // 生成各车间满足情况
        const workshopStatusList = workshops.map(ws => {
            const maxRate = zone === 'WARNING' && elasticK ? ws.max * elasticK : ws.max;
            const allowedRate = zone === 'ALERT' || zone === 'EMERGENCY' ? 0 : maxRate * (0.7 + Math.random() * 0.3);
            const satisfied = allowedRate >= ws.min && allowedRate <= maxRate;
            return {
                id: ws.id,
                name: ws.name,
                max_rate: maxRate.toFixed(2),
                min_rate: ws.min,
                allowed_rate: allowedRate.toFixed(2),
                satisfied: satisfied
            };
        });
        
        // 计算总排放速率和各车间分配
        const totalAllowedRate = zone === 'ALERT' || zone === 'EMERGENCY' ? 0 : Math.min(capacityLimit, processLimit, elasticMaxRate * 7);
        const avgRate = totalAllowedRate / 7;
        
        const actualSum = workshopStatusList.reduce((sum, ws) => sum + parseFloat(ws.allowed_rate), 0);
        const solverProcess = {
            status: solverStatus,
            constraints: [
                {
                    name: '储罐容量约束',
                    order: '约束1',
                    satisfied: actualSum <= capacityLimit,
                    value: zone === 'EMERGENCY' ? '超出上限，无法满足' : 'Σr_i ≤ ' + capacityLimit.toFixed(2) + ' m³/h',
                    formula: 'L + Σ(r_i × T) - C × T ≤ V × SAFE_RATIO',
                    formulaExplain: 'L=当前液位, r_i=车间速率, T=调度周期, C=处理能力, V=储罐容量, SAFE_RATIO=安全系数',
                    equivalent: '等价形式：Σr_i ≤ (V × SAFE_RATIO - L) / T + C',
                    calcVars: {
                        V: 500, SAFE_RATIO: safeRatio, L: Math.round(tankLevel), T: 0.5, C: 60,
                        capacityLimit: capacityLimit.toFixed(2)
                    },
                    // r_i 计算过程
                    riCalc: {
                        totalRate: totalAllowedRate.toFixed(2),
                        workshopCount: 7,
                        avgRate: avgRate.toFixed(2),
                        workshops: workshopStatusList.map(ws => ({
                            name: ws.name,
                            rate: ws.allowed_rate
                        })),
                        actualSum: actualSum.toFixed(2),
                        constraintLimit: capacityLimit.toFixed(2),
                        satisfied: actualSum <= capacityLimit
                    }
                },
                {
                    name: '处理能力约束',
                    order: '约束2',
                    satisfied: true,
                    value: 'Σr_i ≤ ' + processLimit.toFixed(2) + ' m³/h',
                    formula: 'Σr_i ≤ C × PROCESS_BUFFER_RATIO',
                    formulaExplain: 'C=处理能力, PROCESS_BUFFER_RATIO=缓冲系数',
                    calcVars: {
                        C: 60, PROCESS_BUFFER_RATIO: bufferRatio
                    }
                },
                {
                    name: '单车间速率上限约束',
                    order: '约束3',
                    satisfied: true,
                    value: 'r_i ≤ ' + elasticMaxRate.toFixed(2) + ' m³/h',
                    formula: 'r_i ≤ r_max × k',
                    formulaExplain: 'r_max=车间最大速率, k=弹性系数(正常=1.0, 预警区间按公式计算)',
                    calcVars: {
                        r_max: rMax, k: zone === 'WARNING' && elasticK ? elasticK.toFixed(4) : '1.0'
                    },
                    workshopStatus: workshopStatusList
                },
                {
                    name: '单车间最小速率约束',
                    order: '约束4',
                    satisfied: zone === 'NORMAL',
                    value: zone === 'NORMAL' ? 'r_i ≥ ' + rMin + ' m³/h (满足)' : (zone === 'WARNING' ? 'r_i ≥ ' + rMin + ' m³/h (部分压缩)' : '告警/紧急区间跳过此约束'),
                    formula: 'r_i ≥ r_min',
                    formulaExplain: 'r_min=车间最小速率(管道最低流量要求)',
                    calcVars: {
                        r_min: rMin
                    },
                    workshopStatus: workshopStatusList
                }
            ],
            // 弹性系数说明（所有区间都显示）
            elasticFormula: {
                formula: 'k = 1 - (L - 0.8V) / (0.1V) × (1 - MIN_RATE_RATIO)',
                formulaExplain: 'L=当前液位, V=储罐容量, MIN_RATE_RATIO=最低保留比例(默认0.3)',
                calcProcess: zone === 'WARNING' ? 
                    'k = 1 - (' + Math.round(tankLevel) + ' - ' + (500 * 0.8) + ') / (' + (500 * 0.1) + ') × (1 - ' + minRateRatio + ') = ' + (elasticK ? elasticK.toFixed(4) : '-') :
                    (zone === 'NORMAL' ? '正常区间：k = 1.0（无压缩）' : 
                    (zone === 'ALERT' ? '告警区间：k = 0（建议停排）' : '紧急区间：k = 0（建议紧急停排）')),
                result: zone === 'WARNING' && elasticK ? elasticK.toFixed(4) : (zone === 'NORMAL' ? '1.0' : '0'),
                zone: zone
            },
            // 优化目标
            objective: {
                formula: 'Maximize: Σ(w_i × r_i)',
                formulaExplain: 'w_i=车间优先级权重, r_i=车间建议速率',
                note: 'MVP阶段各车间权重统一为1.0，目标退化为最大化总排放速率'
            }
        };

        return {
            alert_record: null,
            input_snapshot: inputSnapshot,
            workshop_snapshots: workshopSnapshots,
            suggestions: suggestions,
            solver_process: solverProcess
        };
    }
};

// 将 Mock 挂载到 window，方便其他文件调用
window.MockData = MockData;
