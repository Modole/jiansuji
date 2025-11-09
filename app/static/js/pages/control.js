// 独立控制页脚本：聚合控制面板相关操作
(function(){
  function init(){
    try {
      if (window.AppPublic && typeof window.AppPublic.__initControlPanel === 'function') {
        window.AppPublic.__initControlPanel();
      } else {
        console.warn('ControlPage: __initControlPanel 未暴露或尚未加载');
      }
    } catch (e) {
      console.error('ControlPage 初始化失败', e);
    }
  }

  function open(){
    try{
      window.AppPublic?.openControlPage?.();
    }catch(_){
      window.AppPublic?.openControlModal?.();
    }
  }

  function submit(){
    try{ window.AppPublic?.submitControlPanel?.(); }
    catch(e){ console.error('ControlPage 提交失败', e); }
  }

  function close(){
    try{ window.AppPublic?.closeControlModal?.(); }
    catch(_){ /* ignore */ }
    if(location.hash === '#control'){
      if(history.length > 1){ history.back(); } else { location.hash = '#home'; }
    }
  }

  window.ControlPage = { init, open, submit, close };
})();