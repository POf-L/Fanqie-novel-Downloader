/* ===================== 标签页系统 ===================== */

class TabSystem {
    static init() {
        document.querySelectorAll('.tab-nav').forEach(nav => {
            nav.querySelectorAll('.tab-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    const targetId = btn.dataset.tab;
                    if (!targetId) return;
                    
                    nav.querySelectorAll('.tab-btn').forEach(t => t.classList.remove('active'));
                    btn.classList.add('active');
                    
                    const container = nav.closest('.card, .main-content, .dashboard-main');
                    if (container) {
                        container.querySelectorAll('.tab-pane').forEach(pane => {
                            pane.classList.remove('active');
                        });
                        const targetPane = container.querySelector(`#tab-${targetId}`);
                        if (targetPane) {
                            targetPane.classList.add('active');
                        }
                    }
                });
            });
        });
    }
}

export default TabSystem;
