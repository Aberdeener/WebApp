function applyTheme() {
    const select = document.getElementById('settings-theme');
    if (select.value === 'dark' || select.value === 'browser' && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        document.getElementsByTagName('body')[0].classList.remove('light');
    } else if (select.value === 'light' || select.value === 'browser') {
        document.getElementsByTagName('body')[0].classList.add('light');
    } else {
        console.warn('unexpected theme setting: ' + select.value)
    }
}

document.addEventListener('DOMContentLoaded', () => {
    applyTheme();
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', applyTheme);
});
