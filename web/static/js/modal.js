class Modal {
    static init() {
        if (document.getElementById('global-modal')) return;

        const modalHtml = `
            <div id="global-modal" class="modal">
                <div class="modal-content">
                    <div class="modal-header">
                        <h3 id="global-modal-title">提示</h3>
                        <button class="modal-close" id="global-modal-close">
                            <iconify-icon icon="line-md:close"></iconify-icon>
                        </button>
                    </div>
                    <div class="modal-body" id="global-modal-body"></div>
                    <div class="modal-footer" id="global-modal-footer"></div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHtml);

        this.modal = document.getElementById('global-modal');
        this.title = document.getElementById('global-modal-title');
        this.body = document.getElementById('global-modal-body');
        this.footer = document.getElementById('global-modal-footer');
        this.closeBtn = document.getElementById('global-modal-close');

        this.closeBtn.onclick = () => this.close();
        
        // Click outside to close
        this.modal.onclick = (e) => {
            if (e.target === this.modal) this.close();
        };

        // Esc key to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isOpen) this.close();
        });
    }

    static get isOpen() {
        return this.modal && this.modal.style.display === 'flex';
    }

    static open() {
        if (!this.modal) this.init();
        this.modal.style.display = 'flex';
        // Animation is handled by CSS
    }

    static close() {
        if (!this.modal) return;
        this.modal.style.display = 'none';
        if (this.onClose) {
            this.onClose();
            this.onClose = null;
        }
    }

    static alert(message, title = '提示') {
        this.init();
        this.title.textContent = title;
        this.body.textContent = message;
        this.footer.innerHTML = `
            <button class="btn btn-primary" onclick="Modal.close()">确定</button>
        `;
        this.onClose = null;
        this.open();
        return new Promise(resolve => {
            this.onClose = resolve;
        });
    }

    static confirm(message, title = '确认') {
        this.init();
        this.title.textContent = title;
        this.body.textContent = message;
        this.footer.innerHTML = `
            <button class="btn btn-secondary" id="modal-cancel-btn">取消</button>
            <button class="btn btn-primary" id="modal-confirm-btn">确定</button>
        `;
        
        return new Promise(resolve => {
            const confirmBtn = document.getElementById('modal-confirm-btn');
            const cancelBtn = document.getElementById('modal-cancel-btn');
            
            const handleConfirm = () => {
                this.close();
                resolve(true);
            };
            
            const handleCancel = () => {
                this.close();
                resolve(false);
            };

            confirmBtn.onclick = handleConfirm;
            cancelBtn.onclick = handleCancel;
            this.onClose = () => resolve(false); // Default to false if closed via X or background
            
            this.open();
        });
    }
}
