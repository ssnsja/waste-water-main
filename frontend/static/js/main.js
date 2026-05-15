// frontend/static/js/main.js
$(function() {
    // 默认主题 (读取 localStorage 或系统偏好)
    var currentTheme = localStorage.getItem('theme') || 'light';
    
    function updateThemeUI(theme) {
      if (theme === 'dark') {
        $('#theme-icon').removeClass('layui-icon-light').addClass('layui-icon-moon');
        $('#theme-label').text('暗色');
      } else {
        $('#theme-icon').removeClass('layui-icon-moon').addClass('layui-icon-light');
        $('#theme-label').text('亮色');
      }
    }

    if (currentTheme === 'dark') {
      document.documentElement.setAttribute('data-theme', 'dark');
    }
    updateThemeUI(currentTheme);
  
    // 时钟更新
    function updateClock() {
      var now = new Date();
      var timeStr = now.toLocaleTimeString();
      $('#system-time').text(timeStr);
    }
    setInterval(updateClock, 1000);
    updateClock();

    // ===== 多标签页管理 =====
    // 页面配置表
    var pageConfig = {
      dashboard:  { title: '调度概览', url: 'views/dashboard.html', closable: false },
      history:    { title: '历史查询', url: 'views/history.html',   closable: true },
      workshops:  { title: '车间管理', url: 'views/workshops.html', closable: true },
      settings:   { title: '系统配置', url: 'views/settings.html',  closable: true }
    };

    // 侧栏导航 data-url → pageId 映射
    var urlToPageId = {
      'views/dashboard.html': 'dashboard',
      'views/history.html':   'history',
      'views/workshops.html': 'workshops',
      'views/settings.html':  'settings'
    };

    // 记录当前激活的 pageId
    var activePageId = 'dashboard';

    layui.use(['element'], function(){
      var element = layui.element;

      // 打开或激活标签
      function openTab(pageId) {
        var config = pageConfig[pageId];
        if (!config) return;

        // 标签已存在则直接切换
        if ($('li[lay-id="' + pageId + '"]').length > 0) {
          element.tabChange('main-tab', pageId);
          return;
        }

        // 创建新标签（Layui 自动包裹 <div class="layui-tab-item">，content 中不要再加）
        element.tabAdd('main-tab', {
          title: config.closable ? config.title + '<i class="layui-icon layui-icon-close tab-close-btn" data-page="' + pageId + '"></i>' : config.title,
          id: pageId,
          content: '<iframe class="page-iframe" data-page="' + pageId + '" src="' + config.url + '" frameborder="0"></iframe>'
        });

        // 给 Layui 自动创建的 .layui-tab-item 添加 data-page 标记
        $('iframe[data-page="' + pageId + '"]').closest('.layui-tab-item').attr('data-page', pageId);

        // 切换到新标签
        element.tabChange('main-tab', pageId);
      }

      // 关闭标签
      function closeTab(pageId) {
        var config = pageConfig[pageId];
        if (!config || !config.closable) return;

        // 通知 iframe 暂停轮询
        notifyIframe(pageId, 'pausePolling');

        // 找到关闭后要切换的标签（前一个或后一个）
        var $tabLi = $('li[lay-id="' + pageId + '"]');
        var $prevLi = $tabLi.prev('li');

        // 删除标签
        element.tabDelete('main-tab', pageId);

        // 切换到前一个标签
        if ($prevLi.length > 0) {
          var prevId = $prevLi.attr('lay-id');
          element.tabChange('main-tab', prevId);
        }
      }

      // 获取 iframe 的 contentWindow
      function getIframeWindow(pageId) {
        var iframe = document.querySelector('iframe[data-page="' + pageId + '"]');
        return iframe ? iframe.contentWindow : null;
      }

      // 通知 iframe 调用指定方法
      function notifyIframe(pageId, method) {
        try {
          var win = getIframeWindow(pageId);
          if (win && typeof win[method] === 'function') {
            win[method]();
          }
        } catch(e) {
          // 跨域或未加载时忽略
        }
      }

      // 监听标签切换
      element.on('tab(main-tab)', function(data) {
        var pageId = $(this).attr('lay-id') || 'dashboard';
        var oldPageId = activePageId;
        activePageId = pageId;

        // 旧标签：暂停轮询
        if (oldPageId && oldPageId !== pageId) {
          notifyIframe(oldPageId, 'pausePolling');
        }

        // 新标签：恢复轮询 + resize图表
        notifyIframe(pageId, 'resumePolling');
        notifyIframe(pageId, 'onPageShow');

        // 同步侧栏高亮
        syncSidebarActive(pageId);
      });

      // 监听标签关闭按钮点击
      $(document).on('click', '.tab-close-btn', function(e) {
        e.stopPropagation();
        var pageId = $(this).attr('data-page');
        closeTab(pageId);
      });

      // 同步侧栏导航高亮
      function syncSidebarActive(pageId) {
        $('.layui-nav-tree .layui-nav-item').removeClass('layui-this');
        var url = pageConfig[pageId] ? pageConfig[pageId].url : '';
        if (url) {
          $('.layui-nav-tree .layui-nav-item a[data-url="' + url + '"]').parent().addClass('layui-this');
        }
      }

      // 监听侧栏导航点击
      element.on('nav(nav-menu)', function(elem) {
        var url = $(this).attr('data-url');
        var pageId = urlToPageId[url];
        if (pageId) {
          openTab(pageId);
        }
      });

      // 监听主题切换按钮
      $('#theme-toggle-btn').on('click', function() {
        currentTheme = currentTheme === 'light' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', currentTheme);
        localStorage.setItem('theme', currentTheme);
        
        updateThemeUI(currentTheme);
    
        // 通知所有已加载的 iframe 更新图表主题
        $('iframe.page-iframe').each(function() {
          try {
            var win = this.contentWindow;
            if (win && typeof win.onThemeChange === 'function') {
              win.onThemeChange(currentTheme);
            }
          } catch(e) {}
        });
      });
    });
  });
  