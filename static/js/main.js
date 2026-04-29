const flashMessages = document.querySelectorAll('.flash');

flashMessages.forEach((flash) => {
    setTimeout(() => {
        flash.style.transition = '0.4s ease';
        flash.style.opacity = '0';
        flash.style.transform = 'translateX(20px)';
        setTimeout(() => flash.remove(), 450);
    }, 3500);
});

const cards = document.querySelectorAll('.book-card, .role-card, .feature-card, .stat-card');

cards.forEach((card) => {
    card.addEventListener('mousemove', (event) => {
        const rect = card.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        card.style.background = `radial-gradient(circle at ${x}px ${y}px, rgba(125, 211, 252, 0.16), rgba(255, 255, 255, 0.08) 38%)`;
    });

    card.addEventListener('mouseleave', () => {
        card.style.background = '';
    });
});
