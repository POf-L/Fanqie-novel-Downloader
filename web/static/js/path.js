/* ===================== 路径字体自适应 ===================== */

function adjustPathFontSize() {
    const pathElements = document.querySelectorAll('.chapter-path, .save-path, .path-display');
    pathElements.forEach(el => {
        const text = el.textContent;
        const maxWidth = el.clientWidth || 300;
        let fontSize = 14;
        el.style.fontSize = `${fontSize}px`;
        
        while (fontSize > 10 && el.scrollWidth > maxWidth) {
            fontSize--;
            el.style.fontSize = `${fontSize}px`;
        }
    });
}

function initPathAutoResize() {
    const observer = new ResizeObserver(() => adjustPathFontSize());
    document.querySelectorAll('.chapter-path, .save-path, .path-display').forEach(el => {
        observer.observe(el);
    });
}

export { adjustPathFontSize, initPathAutoResize };
