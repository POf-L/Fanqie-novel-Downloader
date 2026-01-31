/* ===================== Toast 消息组件 ===================== */

class Toast {
    static container = null;
    static toasts = new Map();
    static idCounter = 0;

    static init() {
        if (this.container) return;
        this.container = document.createElement('div');
        this.container.className = 'toast-container';
        document.body.appendChild(this.container);
    }

    static show(message, type = 'info', duration = 5000) {
        this.init();
        const id = ++this.idCounter;
        
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <div class="toast-icon">${this.getIcon(type)}</div>
            <div class="toast-message">${message}</div>
            <button class="toast-close" onclick="Toast.dismiss(${id})">×</button>
        `;
        
        this.container.appendChild(toast);
        this.toasts.set(id, toast);
        
        requestAnimationFrame(() => toast.classList.add('toast-show'));
        
        if (duration > 0) {
            setTimeout(() => this.dismiss(id), duration);
        }
        
        return id;
    }

    static success(message, duration = 5000) {
        return this.show(message, 'success', duration);
    }

    static error(message, duration = 5000) {
        return this.show(message, 'error', duration);
    }

    static warning(message, duration = 5000) {
        return this.show(message, 'warning', duration);
    }

    static info(message, duration = 5000) {
        return this.show(message, 'info', duration);
    }

    static dismiss(id) {
        const toast = this.toasts.get(id);
        if (!toast) return;
        
        toast.classList.remove('toast-show');
        toast.classList.add('toast-hide');
        
        setTimeout(() => {
            toast.remove();
            this.toasts.delete(id);
        }, 300);
    }

    static getIcon(type) {
        const icons = {
            success: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>',
            error: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>',
            warning: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
            info: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>'
        };
        return icons[type] || icons.info;
    }
}

export default Toast;
