// frontend/static/js/api.js
// 统一 API 请求层，替代 mock.js 的数据获取

var API = {
    _baseUrl: '/api',
    _timeout: 10000,  // 10秒超时

    // 通用请求方法
    _request: function(method, path, data) {
        var opts = {
            url: this._baseUrl + path,
            type: method,
            contentType: 'application/json',
            dataType: 'json',
            timeout: this._timeout
        };
        if (data !== undefined && data !== null) {
            opts.data = JSON.stringify(data);
        }
        return $.ajax(opts);
    },

    // GET 请求
    _get: function(path, params) {
        var opts = {
            url: this._baseUrl + path,
            type: 'GET',
            dataType: 'json',
            timeout: this._timeout
        };
        if (params) {
            opts.data = params;
        }
        return $.ajax(opts);
    },

    // =========================================================================
    // Dashboard 接口
    // =========================================================================

    /** 获取 Dashboard 全部聚合数据 */
    getDashboardOverview: function() {
        return this._get('/dashboard/overview');
    },

    /** 获取最新储罐状态（轮询端点） */
    getTankStatus: function() {
        return this._get('/dashboard/tank-status');
    },

    /** 获取最新一次调度结果 */
    getLatestSchedule: function() {
        return this._get('/dashboard/latest-schedule');
    },

    /** 获取最近 N 条告警 */
    getRecentAlerts: function(limit) {
        var params = {};
        if (limit) params.limit = limit;
        return this._get('/dashboard/recent-alerts', params);
    },

    // =========================================================================
    // History 接口
    // =========================================================================

    /** 分页查询历史调度记录 */
    getHistoryRecords: function(params) {
        return this._get('/history/records', params || {});
    },

    /** 获取历史液位趋势数据 */
    getHistoryTrend: function(params) {
        return this._get('/history/trend', params || {});
    },

    // =========================================================================
    // Schedule 接口
    // =========================================================================

    /** 获取单次调度详情 */
    getScheduleDetail: function(scheduleId) {
        return this._get('/schedule/' + scheduleId + '/detail');
    },

    /** 手动触发一次调度 */
    triggerSchedule: function(tankLevel) {
        return this._request('POST', '/schedule/trigger', { tank_level: tankLevel });
    },

    // =========================================================================
    // Workshop 接口
    // =========================================================================

    /** 获取全部车间列表 */
    getWorkshops: function() {
        return this._get('/workshops');
    },

    /** 新增车间 */
    createWorkshop: function(data) {
        return this._request('POST', '/workshops', data);
    },

    /** 更新车间信息 */
    updateWorkshop: function(workshopId, data) {
        return this._request('PUT', '/workshops/' + workshopId, data);
    },

    /** 切换车间启用状态 */
    updateWorkshopStatus: function(workshopId, isActive) {
        return this._request('PUT', '/workshops/' + workshopId + '/status', { is_active: isActive });
    },

    /** 删除车间（逻辑删除） */
    deleteWorkshop: function(workshopId) {
        return this._request('DELETE', '/workshops/' + workshopId);
    },

    // =========================================================================
    // Config 接口
    // =========================================================================

    /** 获取全部系统配置 */
    getConfig: function() {
        return this._get('/config');
    },

    /** 批量更新系统配置 */
    updateConfig: function(data) {
        return this._request('PUT', '/config', data);
    },

    /** 重启调度器 */
    restartScheduler: function() {
        return this._request('POST', '/config/restart-scheduler');
    },

    // =========================================================================
    // Alert 接口
    // =========================================================================

    /** 分页查询告警记录 */
    getAlerts: function(params) {
        return this._get('/alerts', params || {});
    }
};

// 挂载到 window，方便其他文件调用
window.API = API;
