// frontend/static/js/charts.js
// 图表渲染与数据更新逻辑 (Dashboard) — 已接入真实 API

// ===== 详情弹窗渲染函数（与历史查询页面一致） =====

// 渲染调度输入快照
function renderInputSnapshot(snapshot) {
    var zoneText = snapshot.zone === 'NORMAL' ? '正常' : 
                   snapshot.zone === 'WARNING' ? '预警' : 
                   snapshot.zone === 'ALERT' ? '告警' : 
                   snapshot.zone === 'EMERGENCY' ? '紧急' : snapshot.zone;
    var html = '<div class="detail-grid">' +
        '<div class="detail-item"><label>储罐容量</label><span>' + snapshot.tank_capacity + ' m³</span></div>' +
        '<div class="detail-item"><label>处理能力</label><span>' + snapshot.process_capacity + ' m³/h</span></div>' +
        '<div class="detail-item"><label>调度周期</label><span>' + snapshot.schedule_interval_min + ' 分钟</span></div>' +
        '<div class="detail-item"><label>安全容量系数</label><span>' + snapshot.safe_ratio + '</span></div>' +
        '<div class="detail-item"><label>预警阈值</label><span>' + snapshot.warning_ratio + '</span></div>' +
        '<div class="detail-item"><label>告警阈值</label><span>' + snapshot.alert_ratio + '</span></div>' +
        '<div class="detail-item"><label>紧急阈值</label><span>' + snapshot.emergency_ratio + '</span></div>' +
        '<div class="detail-item"><label>调度时液位</label><span>' + parseFloat(snapshot.tank_level).toFixed(2) + ' m³</span></div>' +
        '<div class="detail-item"><label>液位占比</label><span>' + (parseFloat(snapshot.level_ratio) * 100).toFixed(1) + '%</span></div>' +
        '<div class="detail-item"><label>液位区间</label><span>' + zoneText + '</span></div>' +
        '<div class="detail-item"><label>弹性系数k</label><span>' + (snapshot.elastic_k ? parseFloat(snapshot.elastic_k).toFixed(4) : '-') + '</span></div>' +
        '<div class="detail-item"><label>容量约束上限</label><span>' + (snapshot.capacity_limit ? parseFloat(snapshot.capacity_limit).toFixed(2) : '-') + ' m³/h</span></div>' +
        '<div class="detail-item"><label>处理能力约束</label><span>' + (snapshot.process_limit ? parseFloat(snapshot.process_limit).toFixed(2) : '-') + ' m³/h</span></div>' +
        '<div class="detail-item"><label>生效约束上限</label><span>' + (snapshot.effective_limit ? parseFloat(snapshot.effective_limit).toFixed(2) : '-') + ' m³/h</span></div>' +
        '<div class="detail-item"><label>启用车间数</label><span>' + snapshot.workshop_count + '</span></div>' +
    '</div>';
    $('#input-snapshot').html(html);
}

// 渲染求解过程（前端根据后端返回的参数值按模板渲染，与 mock 逻辑一致）
function renderSolverProcess(solverProcess, snapshot) {
    if (!solverProcess) {
        $('#solver-process').html('<div class="layui-text" style="color: #999; padding: 10px;">求解过程数据不可用</div>');
        return;
    }
    
    var html = '<div class="solver-result">';
    
    // 求解状态
    html += '<div style="margin-bottom: 15px; font-size: 13px; color: var(--text-muted, #666);">';
    html += '<strong>求解状态：</strong>' + (solverProcess.status === 'Optimal' ? '最优解' : solverProcess.status === 'SKIPPED' ? '已跳过（告警/紧急区间）' : solverProcess.status);
    html += '</div>';
    
    // 约束条件列表
    html += '<div class="constraint-list">';
    solverProcess.constraints.forEach(function(c) {
        var iconClass = c.satisfied ? 'satisfied' : 'violated';
        var iconText = c.satisfied ? '✓' : '✗';
        html += '<div class="constraint-item" style="flex-wrap: wrap; margin-bottom: 12px;">';
        html += '<div style="display: flex; align-items: center; width: 100%;">';
        html += '<div class="constraint-icon ' + iconClass + '">' + iconText + '</div>';
        html += '<div class="constraint-label"><strong>' + c.order + '：' + c.name + '</strong></div>';
        html += '<div class="constraint-value">' + c.value + '</div>';
        html += '</div>';
        
        // 公式说明
        html += '<div style="width: 100%; margin-top: 8px; padding: 8px 12px 8px 30px; font-size: 12px; background: rgba(16, 185, 129, 0.03); border-radius: 4px;">';
        html += '<div style="color: #10b981; margin-bottom: 4px;"><i class="layui-icon layui-icon-log" style="margin-right: 4px;"></i>公式：' + c.formula + '</div>';
        if (c.formulaExplain) {
            html += '<div style="color: var(--text-muted, #888); margin-left: 16px;">' + c.formulaExplain + '</div>';
        }
        if (c.equivalent) {
            html += '<div style="color: #ff9800; margin-left: 16px; margin-top: 4px;">' + c.equivalent + '</div>';
        }
        if (c.calcVars) {
            html += '<div style="color: #2196f3; margin-left: 16px; margin-top: 6px; padding-top: 6px; border-top: 1px dashed rgba(255,255,255,0.1);">';
            if (c.name === '储罐容量约束') {
                var V = c.calcVars.V;
                var SAFE_RATIO = c.calcVars.SAFE_RATIO;
                var L = c.calcVars.L;
                var T = c.calcVars.T;
                var C = c.calcVars.C;
                var V_SAFE = V * SAFE_RATIO;
                var V_SAFE_minus_L = V_SAFE - L;
                var divide_T = V_SAFE_minus_L / T;
                html += '→ 分步计算：<br/>';
                html += '<div style="margin-left: 16px; line-height: 1.8;">';
                html += '① V × SAFE_RATIO = ' + V + ' × ' + SAFE_RATIO + ' = ' + V_SAFE.toFixed(2) + ' m³（安全容量上限）<br/>';
                html += '② V × SAFE_RATIO - L = ' + V_SAFE.toFixed(2) + ' - ' + L + ' = ' + V_SAFE_minus_L.toFixed(2) + ' m³（可增量空间）<br/>';
                html += '③ (V × SAFE_RATIO - L) / T = ' + V_SAFE_minus_L.toFixed(2) + ' / ' + T + ' = ' + divide_T.toFixed(2) + ' m³/h（速率上限）<br/>';
                html += '④ Σr_i ≤ ' + divide_T.toFixed(2) + ' + ' + C + ' = <b style="color: #10b981;">' + c.calcVars.capacityLimit + ' m³/h</b>';
                html += '</div>';
                html += '</div>';
                if (c.riCalc && c.riCalc.actualSum !== undefined) {
                    html += '<div style="margin-top: 10px; padding: 10px; background: rgba(33, 150, 243, 0.08); border-radius: 4px;">';
                    html += '<div style="font-size: 11px; color: #2196f3; margin-bottom: 8px;"><i class="layui-icon layui-icon-engine" style="margin-right: 4px;"></i>约束满足验证（代入求解结果校验等价公式）：</div>';
                    html += '<div style="font-size: 12px; color: #ff9800; margin-bottom: 6px;">验证等价公式：Σr_i ≤ (V × SAFE_RATIO - L) / T + C</div>';
                    html += '<div style="font-size: 12px; line-height: 1.8;">';
                    html += '<div style="color: var(--text-muted, #888); margin-bottom: 2px;">① 左侧 Σr_i = 各车间建议速率之和：</div>';
                    html += '<div style="margin-left: 16px;">';
                    c.riCalc.workshops.forEach(function(ws) {
                        html += '<span style="display: inline-block; margin-right: 12px; margin-bottom: 2px;">' + ws.name + ': <span style="font-family: monospace; color: #2196f3;">' + ws.rate + '</span></span>';
                    });
                    html += '<br/>';
                    var wsRates = c.riCalc.workshops.map(function(ws) { return ws.rate; });
                    html += 'Σr_i = ' + wsRates.join(' + ') + ' = <b style="color: #2196f3;">' + c.riCalc.actualSum + '</b> m³/h';
                    html += '</div>';
                    html += '<div style="color: var(--text-muted, #888); margin-top: 6px; margin-bottom: 2px;">② 右侧约束上限（已在上方分步计算）= <b style="color: #10b981;">' + c.riCalc.constraintLimit + '</b> m³/h</div>';
                    html += '<div style="margin-top: 8px; padding-top: 8px; border-top: 1px dashed rgba(255,255,255,0.1);">';
                    html += '<div style="color: var(--text-muted, #888); margin-bottom: 4px;">③ 比较验证：</div>';
                    var satisfied = c.riCalc.satisfied;
                    var compareColor = satisfied ? '#10b981' : '#ef4444';
                    html += '<div style="margin-left: 16px;">';
                    html += c.riCalc.actualSum + ' ≤ ' + c.riCalc.constraintLimit + ' → <b style="color: ' + compareColor + ';">' + (satisfied ? '✓ 满足约束' : '✗ 违反约束') + '</b>';
                    html += '</div>';
                    html += '</div>';
                    html += '</div>';
                    html += '</div>';
                }
            } else if (c.name === '处理能力约束') {
                html += '→ 计算：C × PROCESS_BUFFER_RATIO = ' + c.calcVars.C + ' × ' + c.calcVars.PROCESS_BUFFER_RATIO + ' = ' + (c.calcVars.C * c.calcVars.PROCESS_BUFFER_RATIO) + ' m³/h';
            } else if (c.name === '单车间速率上限约束') {
                var k = c.calcVars.k;
                var rMax = c.calcVars.r_max;
                html += '→ 计算：r_max × k = ' + rMax + ' × ' + k + ' = ' + (rMax * parseFloat(k)).toFixed(2) + ' m³/h';
            } else if (c.name === '单车间最小速率约束') {
                html += '→ r_min = ' + c.calcVars.r_min + ' m³/h';
            }
            html += '</div>';
        }
        // 车间满足状态列表
        if (c.workshopStatus) {
            html += '<div class="workshop-status-list">';
            html += '<div style="font-size: 11px; color: var(--text-muted, #888); margin-bottom: 4px;">各车间满足情况：</div>';
            c.workshopStatus.forEach(function(ws) {
                html += '<span class="workshop-status-item">';
                html += '<span class="ws-name">' + ws.name + '</span>';
                html += '<span class="ws-rate">' + ws.allowed_rate + '</span>';
                html += '<span class="' + (ws.satisfied ? 'ws-check' : 'ws-cross') + '">' + (ws.satisfied ? '✓' : '✗') + '</span>';
                html += '</span>';
            });
            html += '</div>';
        }
        html += '</div>';
        html += '</div>';
    });
    html += '</div>';
    
    // 弹性系数说明
    if (solverProcess.elasticFormula) {
        var ef = solverProcess.elasticFormula;
        var zoneColor = ef.zone === 'WARNING' ? '#ff9800' : (ef.zone === 'NORMAL' ? '#10b981' : '#ef4444');
        var zoneBgColor = ef.zone === 'WARNING' ? 'rgba(255, 152, 0, 0.1)' : (ef.zone === 'NORMAL' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)');
        var zoneTitle = ef.zone === 'WARNING' ? '弹性系数计算（预警区间）' : (ef.zone === 'NORMAL' ? '弹性系数（正常区间）' : '弹性系数（' + (ef.zone === 'ALERT' ? '告警' : '紧急') + '区间）');
        html += '<div style="margin-top: 15px; padding: 10px 12px; background: ' + zoneBgColor + '; border-radius: 4px; border-left: 3px solid ' + zoneColor + ';">';
        html += '<div style="font-weight: bold; color: ' + zoneColor + '; margin-bottom: 8px;"><i class="layui-icon layui-icon-rate" style="margin-right: 4px;"></i>' + zoneTitle + '</div>';
        html += '<div style="font-size: 12px; color: var(--text-muted, #888);">';
        if (ef.zone === 'WARNING') {
            html += '<div style="color: #10b981;">公式：' + ef.formula + '</div>';
            html += '<div style="margin-left: 16px;">' + ef.formulaExplain + '</div>';
            html += '<div style="color: #2196f3; margin-top: 8px; padding-top: 8px; border-top: 1px dashed rgba(255,255,255,0.1);">→ 计算：' + ef.calcProcess + '</div>';
        } else {
            html += '<div style="color: #10b981;">公式：' + ef.formula + '</div>';
            html += '<div style="margin-left: 16px;">' + ef.formulaExplain + '</div>';
            html += '<div style="color: ' + zoneColor + '; margin-top: 8px; padding-top: 8px; border-top: 1px dashed rgba(255,255,255,0.1);">→ ' + ef.calcProcess + '</div>';
        }
        html += '</div></div>';
    }
    
    // 优化目标
    if (solverProcess.objective) {
        var obj = solverProcess.objective;
        html += '<div style="margin-top: 15px; padding: 10px 12px; background: rgba(33, 150, 243, 0.1); border-radius: 4px; border-left: 3px solid #2196f3;">';
        html += '<div style="font-weight: bold; color: #2196f3; margin-bottom: 8px;"><i class="layui-icon layui-icon-chart" style="margin-right: 4px;"></i>优化目标</div>';
        html += '<div style="font-size: 12px;">';
        html += '<div style="color: #10b981;">' + obj.formula + '</div>';
        html += '<div style="color: var(--text-muted, #888); margin-left: 16px;">' + obj.formulaExplain + '</div>';
        html += '<div style="color: #ff9800; margin-top: 6px; margin-left: 16px;">' + obj.note + '</div>';
        html += '</div></div>';
    }
    
    html += '</div>';
    $('#solver-process').html(html);
}

// 初始化浮动导航交互
function initDetailNav() {
    var $nav = $('#detail-nav');
    var $wrapper = $('.detail-wrapper');
    var sectionPositions = {};
    var scrollProgrammatic = false;
    
    function calculatePositions() {
        sectionPositions = {};
        $wrapper.find('h4').each(function() {
            var $section = $(this);
            var targetDiv = $section.next('div');
            if (targetDiv.length) {
                var targetId = targetDiv.attr('id');
                sectionPositions[targetId] = $section[0].offsetTop;
            }
        });
    }
    calculatePositions();
    
    $nav.find('a').on('click', function() {
        var target = $(this).data('target');
        if (sectionPositions[target] !== undefined) {
            scrollProgrammatic = true;
            var scrollTo = Math.max(0, sectionPositions[target] - 10);
            $wrapper.stop().animate({ scrollTop: scrollTo }, 300, function() {
                setTimeout(function() { scrollProgrammatic = false; }, 100);
            });
            $nav.find('a').removeClass('active');
            $(this).addClass('active');
        }
    });
    
    $wrapper.on('scroll', function() {
        if (scrollProgrammatic) return;
        var scrollTop = $wrapper.scrollTop();
        var found = false;
        var sortedSections = Object.keys(sectionPositions).map(function(id) {
            return { id: id, pos: sectionPositions[id] };
        }).sort(function(a, b) { return a.pos - b.pos; });
        for (var i = sortedSections.length - 1; i >= 0; i--) {
            if (sortedSections[i].pos <= scrollTop + 80) {
                $nav.find('a').removeClass('active');
                $nav.find('a[data-target="' + sortedSections[i].id + '"]').addClass('active');
                found = true;
                break;
            }
        }
        if (!found && sortedSections.length > 0) {
            $nav.find('a').removeClass('active');
            $nav.find('a[data-target="' + sortedSections[0].id + '"]').addClass('active');
        }
    });
}

// 根据后端返回的 input_snapshot 数据，在前端渲染求解过程
function buildSolverProcessFromSnapshot(inputSnapshot, suggestions) {
    var zone = inputSnapshot.zone;
    var V = inputSnapshot.tank_capacity;
    var L = inputSnapshot.tank_level;
    var T = inputSnapshot.schedule_interval_min / 60.0;
    var C = inputSnapshot.process_capacity;
    var safeRatio = inputSnapshot.safe_ratio;
    var bufferRatio = inputSnapshot.process_buffer_ratio;
    var minRateRatio = inputSnapshot.min_rate_ratio;
    var elasticK = inputSnapshot.elastic_k;
    // ALERT/EMERGENCY 区间后端不计算约束值，需 null 安全处理
    var capacityLimit = inputSnapshot.capacity_limit;
    var processLimit = inputSnapshot.process_limit;
    var effectiveLimit = inputSnapshot.effective_limit;
    var isSkipped = zone === 'ALERT' || zone === 'EMERGENCY';
    var solverStatus = suggestions.length > 0 ? suggestions[0].solver_status : 'SKIPPED';

    // 计算弹性上限（从车间快照获取）
    var rMax = suggestions.length > 0 ? Math.max.apply(null, suggestions.map(function(s) { return parseFloat(s.allowed_rate) || 0; })) : 12;
    var elasticMaxRate = (zone === 'WARNING' && elasticK) ? rMax * elasticK : rMax;

    // 生成各车间满足情况
    var workshopStatusList = suggestions.map(function(s) {
        var maxRate = parseFloat(s.allowed_rate) || 0;
        var satisfied = zone !== 'ALERT' && zone !== 'EMERGENCY' ? maxRate >= 2 : true;
        return {
            id: s.workshop_id,
            name: s.workshop_name,
            max_rate: parseFloat(s.allowed_rate).toFixed(2),
            min_rate: 2,
            allowed_rate: parseFloat(s.allowed_rate).toFixed(2),
            satisfied: satisfied
        };
    });

    var totalAllowedRate = suggestions.reduce(function(sum, s) { return sum + (parseFloat(s.allowed_rate) || 0); }, 0);
    var avgRate = suggestions.length > 0 ? totalAllowedRate / suggestions.length : 0;
    var actualSum = totalAllowedRate.toFixed(2);

    var solverProcess = {
        status: solverStatus,
        constraints: [
            {
                name: '储罐容量约束',
                order: '约束1',
                satisfied: isSkipped ? false : totalAllowedRate <= capacityLimit,
                value: isSkipped ? '求解已跳过（告警/紧急区间）' : 'Σr_i ≤ ' + capacityLimit.toFixed(2) + ' m³/h',
                formula: 'L + Σ(r_i × T) - C × T ≤ V × SAFE_RATIO',
                formulaExplain: 'L=当前液位, r_i=车间速率, T=调度周期, C=处理能力, V=储罐容量, SAFE_RATIO=安全系数',
                equivalent: isSkipped ? null : '等价形式：Σr_i ≤ (V × SAFE_RATIO - L) / T + C',
                calcVars: isSkipped ? null : {
                    V: V, SAFE_RATIO: safeRatio, L: Math.round(L), T: T, C: C,
                    capacityLimit: capacityLimit.toFixed(2)
                },
                riCalc: isSkipped ? null : {
                    totalRate: totalAllowedRate.toFixed(2),
                    workshopCount: suggestions.length,
                    avgRate: avgRate.toFixed(2),
                    workshops: suggestions.map(function(s) { return { name: s.workshop_name, rate: parseFloat(s.allowed_rate).toFixed(2) }; }),
                    actualSum: actualSum,
                    constraintLimit: capacityLimit.toFixed(2),
                    satisfied: totalAllowedRate <= capacityLimit
                }
            },
            {
                name: '处理能力约束',
                order: '约束2',
                satisfied: true,
                value: isSkipped ? '求解已跳过' : 'Σr_i ≤ ' + processLimit.toFixed(2) + ' m³/h',
                formula: 'Σr_i ≤ C × PROCESS_BUFFER_RATIO',
                formulaExplain: 'C=处理能力, PROCESS_BUFFER_RATIO=缓冲系数',
                calcVars: isSkipped ? null : { C: C, PROCESS_BUFFER_RATIO: bufferRatio }
            },
            {
                name: '单车间速率上限约束',
                order: '约束3',
                satisfied: true,
                value: isSkipped ? '求解已跳过' : 'r_i ≤ ' + elasticMaxRate.toFixed(2) + ' m³/h',
                formula: 'r_i ≤ r_max × k',
                formulaExplain: 'r_max=车间最大速率, k=弹性系数(正常=1.0, 预警区间按公式计算)',
                calcVars: isSkipped ? null : { r_max: rMax, k: (zone === 'WARNING' && elasticK) ? elasticK.toFixed(4) : '1.0' },
                workshopStatus: isSkipped ? null : workshopStatusList
            },
            {
                name: '单车间最小速率约束',
                order: '约束4',
                satisfied: zone === 'NORMAL',
                value: zone === 'NORMAL' ? 'r_i ≥ 2 m³/h (满足)' : (zone === 'WARNING' ? 'r_i ≥ 2 m³/h (部分压缩)' : '告警/紧急区间跳过此约束'),
                formula: 'r_i ≥ r_min',
                formulaExplain: 'r_min=车间最小速率(管道最低流量要求)',
                calcVars: { r_min: 2 },
                workshopStatus: isSkipped ? null : workshopStatusList
            }
        ],
        elasticFormula: {
            formula: 'k = 1 - (L - 0.8V) / (0.1V) × (1 - MIN_RATE_RATIO)',
            formulaExplain: 'L=当前液位, V=储罐容量, MIN_RATE_RATIO=最低保留比例(默认0.3)',
            calcProcess: zone === 'WARNING' ? 
                'k = 1 - (' + Math.round(L) + ' - ' + (V * inputSnapshot.warning_ratio) + ') / (' + (V * 0.1) + ') × (1 - ' + minRateRatio + ') = ' + (elasticK ? elasticK.toFixed(4) : '-') :
                (zone === 'NORMAL' ? '正常区间：k = 1.0（无压缩）' : 
                (zone === 'ALERT' ? '告警区间：k = 0（建议停排）' : '紧急区间：k = 0（建议紧急停排）')),
            result: zone === 'WARNING' && elasticK ? elasticK.toFixed(4) : (zone === 'NORMAL' ? '1.0' : '0'),
            zone: zone
        },
        objective: {
            formula: 'Maximize: Σ(w_i × r_i)',
            formulaExplain: 'w_i=车间优先级权重, r_i=车间建议速率',
            note: 'MVP阶段各车间权重统一为1.0，目标退化为最大化总排放速率'
        }
    };
    return solverProcess;
}

// ===== Dashboard 主逻辑 =====

// 历史趋势图表渲染（供 history.html 共享调用）
function renderTrendChart(chart, trendData) {
    var option = {
        tooltip: { trigger: 'axis' },
        legend: { data: ['实际液位', '预测液位'] },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: { type: 'category', boundaryGap: false, data: trendData.times },
        yAxis: { type: 'value', name: '液位 (m³)' },
        series: [
            {
                name: '实际液位',
                type: 'line',
                data: trendData.levels,
                itemStyle: { color: '#16baaa' },
                areaStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: 'rgba(22, 186, 170, 0.3)' },
                        { offset: 1, color: 'rgba(22, 186, 170, 0.1)' }
                    ])
                }
            },
            {
                name: '预测液位',
                type: 'line',
                data: trendData.predicted,
                itemStyle: { color: '#ffb800' },
                lineStyle: { type: 'dashed' }
            }
        ]
    };
    chart.setOption(option, true);
}

// 全局变量
var currentScheduleId = null;
var gaugeChart = null;
var barChart = null;
var pollTimer = null;
var pollIntervalMs = 30000; // 默认30秒

$(function() {
    // 仅在 Dashboard 页面（存在 gauge-chart 元素）才初始化仪表盘/柱状图
    var gaugeEl = document.getElementById('gauge-chart');
    var barEl = document.getElementById('bar-chart');

    if (!gaugeEl && !barEl) return; // 非 Dashboard 页面，跳过全部初始化

    // 初始化图表
    if (gaugeEl) gaugeChart = echarts.init(gaugeEl);
    if (barEl) barChart = echarts.init(barEl);

    // 从 API 获取初始数据
    loadDashboardData();

    // 启动轮询
    startPolling();

    // 查看详情链接点击事件
    $('#view-detail-link').on('click', function() {
        if (!currentScheduleId) {
            layui.use('layer', function(){ layui.layer.msg('暂无调度数据'); });
            return;
        }
        showScheduleDetail(currentScheduleId);
    });

    // 处理主题切换
    window.onThemeChange = function(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        applyChartTheme(theme);
    };

    let currentTheme = localStorage.getItem('theme') || 'light';
    if(currentTheme === 'dark') {
        window.onThemeChange('dark');
    }

    // 窗口缩放自适应
    window.addEventListener('resize', function() {
        if (gaugeChart) gaugeChart.resize();
        if (barChart) barChart.resize();
        syncCardHeights();
    });

    // 延迟执行，等layui表格渲染完成
    setTimeout(syncCardHeights, 300);
});

// 加载 Dashboard 全部聚合数据
function loadDashboardData() {
    window.API.getDashboardOverview().done(function(resp) {
        if (resp.status !== 200) {
            console.error('获取概览数据失败:', resp.message);
            return;
        }
        var data = resp.data;
        updateDashboard(data);
    }).fail(function(xhr, status, error) {
        console.error('获取概览数据请求失败:', status, error);
    });
}

// 更新 Dashboard 页面
function updateDashboard(data) {
    var tankStatus = data.tank_status;
    var scheduleResults = data.schedule_results;
    var alerts = data.alerts || [];
    var activeWorkshopCount = data.active_workshop_count || 0;
    var currentCycle = data.current_cycle;
    var nextCycle = data.next_cycle;

    // 更新 KPI 卡片
    if (tankStatus) {
        $('#kpi-level').text(tankStatus.level + ' (' + tankStatus.ratio + '%)');
        var statusMap = {
            'NORMAL': { text: '正常', class: 'kpi-status-normal' },
            'WARNING': { text: '预警', class: 'kpi-status-warning' },
            'ALERT': { text: '告警', class: 'kpi-status-alert' },
            'EMERGENCY': { text: '紧急', class: 'kpi-status-emergency' }
        };
        var sInfo = statusMap[tankStatus.status] || { text: tankStatus.status, class: '' };
        $('#kpi-status').text(sInfo.text).addClass(sInfo.class);
    }

    if (scheduleResults) {
        $('#kpi-total-rate').text(scheduleResults.total_rate);
        currentScheduleId = scheduleResults.schedule_id;
    } else {
        $('#kpi-total-rate').text('--');
        currentScheduleId = null;
    }

    $('#kpi-workshops').text(activeWorkshopCount);

    // 调度周期时间
    if (currentCycle) {
        $('#kpi-current-cycle').text(formatAPITime(currentCycle));
    }
    if (nextCycle) {
        $('#kpi-next-cycle').text(formatAPITime(nextCycle));
    }

    // 渲染仪表盘
    renderGaugeChart(tankStatus);

    // 渲染柱状图
    renderBarChart(scheduleResults);

    // 渲染表格
    renderScheduleTable(scheduleResults);

    // 渲染告警
    renderAlerts(alerts);
}

// 格式化 API 返回的 ISO 时间
function formatAPITime(isoStr) {
    if (!isoStr) return '--';
    try {
        var d = new Date(isoStr);
        var mm = (d.getMonth() + 1).toString().padStart(2, '0');
        var dd = d.getDate().toString().padStart(2, '0');
        var hh = d.getHours().toString().padStart(2, '0');
        var mi = d.getMinutes().toString().padStart(2, '0');
        return mm + '/' + dd + ' ' + hh + ':' + mi;
    } catch(e) {
        return isoStr;
    }
}

// 渲染仪表盘
function renderGaugeChart(tankStatus) {
    var level = tankStatus ? tankStatus.level : 0;
    var gaugeOption = {
        series: [{
            type: 'gauge',
            max: 500,
            axisLine: {
                lineStyle: {
                    width: 15,
                    color: [
                        [0.8, '#10b981'],
                        [0.9, '#ffb800'],
                        [0.95, '#ff5722'],
                        [1, '#c00000']
                    ]
                }
            },
            pointer: { itemStyle: { color: 'auto' } },
            axisTick: { distance: -15, length: 8, lineStyle: { color: '#fff', width: 2 } },
            splitLine: { distance: -15, length: 15, lineStyle: { color: '#fff', width: 3 } },
            axisLabel: { color: 'inherit', distance: 25, fontSize: 10 },
            detail: { valueAnimation: true, formatter: '{value} m³', color: 'inherit', fontSize: 20 },
            data: [{ value: parseFloat(level) || 0 }]
        }]
    };
    gaugeChart.setOption(gaugeOption);
}

// 渲染柱状图
function renderBarChart(scheduleResults) {
    if (!scheduleResults || !scheduleResults.results) {
        barChart.setOption({ series: [] });
        return;
    }
    var results = scheduleResults.results;
    var wsNames = results.map(function(item) { return item.workshop_name; });
    var maxRates = results.map(function(item) { return parseFloat(item.max_rate) || 0; });
    var allowedRates = results.map(function(item) { return parseFloat(item.allowed_rate) || 0; });
    
    var barOption = {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        legend: { data: ['建议排放速率', '最大排放能力'] },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: { type: 'category', data: wsNames, axisLabel: { interval: 0, rotate: 30 } },
        yAxis: { type: 'value', name: '速率 (m³/h)' },
        series: [
            {
                name: '建议排放速率',
                type: 'bar',
                data: allowedRates,
                itemStyle: { color: '#10b981' }
            },
            {
                name: '最大排放能力',
                type: 'line',
                data: maxRates,
                itemStyle: { color: '#999', type: 'dashed' },
                symbol: 'none'
            }
        ]
    };
    barChart.setOption(barOption);
}

// 渲染表格
function renderScheduleTable(scheduleResults) {
    layui.use('table', function(){
        var table = layui.table;
        var results = (scheduleResults && scheduleResults.results) ? scheduleResults.results : [];
        table.render({
            elem: '#schedule-table',
            data: results,
            page: false,
            cols: [[
                {field: 'workshop_id', title: '编号', width: 100},
                {field: 'workshop_name', title: '车间名称'},
                {field: 'max_rate', title: '最大速率(m³/h)', width: 150, align: 'right'},
                {field: 'allowed_rate', title: '建议速率(m³/h)', width: 150, align: 'right', templet: function(d){
                    return '<span style="color: var(--primary-color); font-weight: bold;">' + d.allowed_rate + '</span>';
                }},
                {field: 'allowed_volume', title: '推算排放量(m³)', width: 150, align: 'right'}
            ]]
        });
    });
}

// 渲染告警
function renderAlerts(alerts) {
    var levelTextMap = {'NORMAL':'正常','WARNING':'预警','ALERT':'告警','EMERGENCY':'紧急'};
    var levelClassMap = {'NORMAL':'tag-normal','WARNING':'tag-warning','ALERT':'tag-alert','EMERGENCY':'tag-emergency'};
    var alertHtml = alerts.map(function(a, idx) {
        var timeStr = formatAPITime(a.alert_time);
        return '<div class="alert-item" data-idx="' + idx + '">' +
            '<span class="time">' + timeStr + '</span>' +
            '<span class="alert-level-tag ' + (levelClassMap[a.alert_level] || '') + '">' + (levelTextMap[a.alert_level] || a.alert_level) + '</span>' +
            '<span>' + a.alert_message + '</span>' +
        '</div>';
    }).join('');
    $('#alert-container').html('<div class="alert-ticker-inner">' + alertHtml + '</div>');

    // 走马灯自动滚动
    var tickerEl = document.getElementById('alert-container');
    var innerEl = tickerEl.querySelector('.alert-ticker-inner');
    if (!innerEl || alerts.length === 0) return;

    var tickerPaused = false;
    var currentStep = 0;

    // 仅有多条告警时才复制内容实现无缝滚动
    if (alerts.length > 1) {
        innerEl.innerHTML += innerEl.innerHTML;
    }

    function getAlertItemHeight() {
        var firstItem = innerEl.querySelector('.alert-item');
        return firstItem ? firstItem.offsetHeight : 50;
    }

    clearInterval(window._tickerInterval);
    // 只有多条告警时才启用自动滚动
    if (alerts.length > 1) {
        window._tickerInterval = setInterval(function() {
            if (tickerPaused) return;
            currentStep++;
            var halfCount = alerts.length;
            if (currentStep >= halfCount) {
                currentStep = 0;
            }
            var itemH = getAlertItemHeight();
            innerEl.style.transform = 'translateY(-' + (currentStep * itemH) + 'px)';
        }, 1000);
    }

    $(tickerEl).off('mouseenter mouseleave');
    $(tickerEl).on('mouseenter', function() { tickerPaused = true; })
               .on('mouseleave', function() { tickerPaused = false; });
}

// 显示调度详情弹窗
function showScheduleDetail(scheduleId) {
    layui.use(['table', 'layer'], function(){
        var table = layui.table;
        var layer = layui.layer;

        window.API.getScheduleDetail(scheduleId).done(function(resp) {
            if (resp.status !== 200) {
                layer.msg('获取调度详情失败: ' + resp.message);
                return;
            }
            var detailData = resp.data;

            // 使用后端数据 + 前端模板渲染求解过程
            var solverProcess = buildSolverProcessFromSnapshot(
                detailData.input_snapshot, 
                detailData.suggestions
            );

            layer.open({
                type: 1,
                title: '本周期调度详情',
                area: ['900px', '600px'],
                maxWidth: 900,
                content: $('#detailTpl').html(),
                success: function(layero, index) {
                    // 渲染调度输入快照
                    renderInputSnapshot(detailData.input_snapshot);
                    
                    // 渲染车间配置快照表格
                    table.render({
                        elem: '#workshop-snapshot-table',
                        data: detailData.workshop_snapshots,
                        page: false,
                        limit: 10,
                        cols: [[
                            {field: 'workshop_id', title: '车间编号', minWidth: 80},
                            {field: 'workshop_name', title: '车间名称', minWidth: 100},
                            {field: 'max_discharge_rate', title: '最大速率(m³/h)', minWidth: 120, align: 'right'},
                            {field: 'min_discharge_rate', title: '最小速率(m³/h)', minWidth: 120, align: 'right'},
                            {field: 'priority_weight', title: '优先级权重', minWidth: 100, align: 'center'},
                            {field: 'elastic_max_rate', title: '弹性上限(m³/h)', minWidth: 130, align: 'right', templet: function(d){
                                return d.elastic_max_rate || '-';
                            }}
                        ]]
                    });
                    
                    // 渲染建议排放表格
                    table.render({
                        elem: '#suggestion-table',
                        data: detailData.suggestions,
                        page: false,
                        limit: 10,
                        cols: [[
                            {field: 'workshop_id', title: '车间编号', minWidth: 80},
                            {field: 'workshop_name', title: '车间名称', minWidth: 100},
                            {field: 'allowed_rate', title: '建议速率(m³/h)', minWidth: 130, align: 'right'},
                            {field: 'allowed_volume', title: '建议排放量(m³)', minWidth: 140, align: 'right'},
                            {field: 'schedule_status', title: '调度状态', minWidth: 100, templet: function(d){
                                var statusText = d.schedule_status === 'NORMAL' ? '正常' : 
                                               d.schedule_status === 'WARNING' ? '预警' : 
                                               d.schedule_status === 'ALERT' ? '告警' : 
                                               d.schedule_status === 'EMERGENCY' ? '紧急' : d.schedule_status;
                                var colorCls = d.schedule_status === 'NORMAL' ? 'badge-soft-green' : 
                                               d.schedule_status === 'WARNING' ? 'badge-soft-yellow' : 
                                               d.schedule_status === 'ALERT' ? 'badge-soft-red' : 
                                               d.schedule_status === 'EMERGENCY' ? 'badge-soft-dark' : 'badge-soft-gray';
                                return '<span class="status-badge ' + colorCls + '">' + statusText + '</span>';
                            }}
                        ]]
                    });
                    
                    // 渲染求解过程（使用前端模板从后端数据渲染）
                    renderSolverProcess(solverProcess, detailData.input_snapshot);
                    
                    // 初始化浮动导航交互
                    initDetailNav();
                }
            });
        }).fail(function() {
            layer.msg('获取调度详情失败，请检查网络连接');
        });
    });
}

// 启动轮询
function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(function() {
        if (document.hidden) return; // 页面不可见时暂停
        pollDashboardData();
    }, pollIntervalMs);
}

// 轮询数据更新
function pollDashboardData() {
    $.when(
        window.API.getTankStatus(),
        window.API.getLatestSchedule(),
        window.API.getRecentAlerts(10)
    ).done(function(tankResp, scheduleResp, alertsResp) {
        // 更新储罐状态
        if (tankResp[0] && tankResp[0].status === 200 && tankResp[0].data) {
            var ts = tankResp[0].data;
            $('#kpi-level').text(ts.level + ' (' + ts.ratio + '%)');
            var statusMap = {
                'NORMAL': { text: '正常', class: 'kpi-status-normal' },
                'WARNING': { text: '预警', class: 'kpi-status-warning' },
                'ALERT': { text: '告警', class: 'kpi-status-alert' },
                'EMERGENCY': { text: '紧急', class: 'kpi-status-emergency' }
            };
            var sInfo = statusMap[ts.status] || { text: ts.status, class: '' };
            $('#kpi-status').text(sInfo.text).addClass(sInfo.class);
            renderGaugeChart(ts);
        }

        // 更新调度结果
        if (scheduleResp[0] && scheduleResp[0].status === 200 && scheduleResp[0].data) {
            var sr = scheduleResp[0].data;
            $('#kpi-total-rate').text(sr.total_rate);
            currentScheduleId = sr.schedule_id;
            renderBarChart(sr);
            renderScheduleTable(sr);
        }

        // 更新告警
        if (alertsResp[0] && alertsResp[0].status === 200 && alertsResp[0].data) {
            renderAlerts(alertsResp[0].data);
        }
    }).fail(function() {
        console.warn('轮询数据更新失败，将在下次轮询重试');
    });
}

// 图表主题适配
function applyChartTheme(theme) {
    if (!gaugeChart || !barChart) return;
    let textColor = theme === 'dark' ? '#e0e0e0' : '#333';
    let splitLineColor = theme === 'dark' ? '#333' : '#ccc';
    let primaryColor = theme === 'dark' ? '#2ADB5C' : '#10b981';

    barChart.setOption({
        legend: { textStyle: { color: textColor } },
        xAxis: { axisLabel: { color: textColor }, axisLine: { lineStyle: { color: splitLineColor } } },
        yAxis: { nameTextStyle: { color: textColor }, axisLabel: { color: textColor }, splitLine: { lineStyle: { color: splitLineColor } } },
        series: [{ name: '建议排放速率', itemStyle: { color: primaryColor } }]
    });

    gaugeChart.setOption({
        series: [{
            axisLine: {
                lineStyle: {
                    color: [
                        [0.8, primaryColor], 
                        [0.9, '#ffa000'],
                        [0.95, '#ff5252'],
                        [1, '#d32f2f']
                    ]
                }
            }
        }]
    });

    var $dots = $('.gauge-legend-dot');
    $dots.eq(0).css('background', primaryColor);
    $dots.eq(1).css('background', '#ffa000');
    $dots.eq(2).css('background', '#ff5252');
    $dots.eq(3).css('background', '#d32f2f');
}

// 同行卡片等高
function syncCardHeights() {
    $('#gauge-chart').closest('.layui-card').css('min-height', '');
    $('#bar-chart').closest('.layui-card').css('min-height', '');
    $('#schedule-table').closest('.layui-card').css('min-height', '');
    $('#alert-container').closest('.layui-card').css('min-height', '');
    $('#alert-container').css('height', '');
    $('#gauge-chart').css('height', '280px');
    if (gaugeChart) gaugeChart.resize();

    var $gaugeCard = $('#gauge-chart').closest('.layui-card');
    var $barCard = $('#bar-chart').closest('.layui-card');
    var row2H = Math.max($gaugeCard.outerHeight(), $barCard.outerHeight());
    $gaugeCard.css('min-height', row2H);
    $barCard.css('min-height', row2H);
    var gBorderT = parseFloat($gaugeCard.css('border-top-width')) || 0;
    var gBorderB = parseFloat($gaugeCard.css('border-bottom-width')) || 0;
    var gHeaderH = $gaugeCard.find('.layui-card-header').outerHeight();
    var gBody = $gaugeCard.find('.layui-card-body');
    var gBodyPadT = parseFloat(gBody.css('padding-top')) || 0;
    var gBodyPadB = parseFloat(gBody.css('padding-bottom')) || 0;
    var gLegendH = $gaugeCard.find('.gauge-legend').outerHeight(true) || 0;
    var gaugeAvailH = row2H - gBorderT - gBorderB - gHeaderH - gBodyPadT - gBodyPadB - gLegendH;
    $('#gauge-chart').css('height', Math.max(200, gaugeAvailH) + 'px');
    if (gaugeChart) gaugeChart.resize();

    var $tableCard = $('#schedule-table').closest('.layui-card');
    var $alertCard = $('#alert-container').closest('.layui-card');
    var row3H = Math.max($tableCard.outerHeight(), $alertCard.outerHeight());
    $tableCard.css('min-height', row3H);
    $alertCard.css('min-height', row3H);
    var aBorderT = parseFloat($alertCard.css('border-top-width')) || 0;
    var aBorderB = parseFloat($alertCard.css('border-bottom-width')) || 0;
    var aHeaderH = $alertCard.find('.layui-card-header').outerHeight();
    var aBody = $alertCard.find('.layui-card-body');
    var aBodyPadT = parseFloat(aBody.css('padding-top')) || 0;
    var aBodyPadB = parseFloat(aBody.css('padding-bottom')) || 0;
    var alertAvailH = row3H - aBorderT - aBorderB - aHeaderH - aBodyPadT - aBodyPadB;
    $('#alert-container').css('height', alertAvailH + 'px');
}

// ===== 多标签页状态保持接口（供父页面调用） =====

// 暂停轮询
function pausePolling() {
    if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
    }
}

// 恢复轮询
function resumePolling() {
    if (!pollTimer) {
        startPolling();
        pollDashboardData(); // 立即刷新一次
    }
}

// 标签页重新显示时触发（resize 图表）
function onPageShow() {
    if (gaugeChart) gaugeChart.resize();
    if (barChart) barChart.resize();
    syncCardHeights();
}
