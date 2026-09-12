/**
 * Entry point for the login page. Bundles Alpine so the page works offline
 * (no CDN dependency), the same way the main app does.
 */
import Alpine from 'alpinejs';

window.Alpine = Alpine;

export function loginApp() {
    return {
        username: '',
        password: '',
        loading: false,
        error: null,

        async login() {
            this.error = null;
            this.loading = true;

            try {
                const response = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        username: this.username,
                        password: this.password
                    }),
                    credentials: 'same-origin'
                });

                const data = await response.json();

                if (response.ok) {
                    // Redirect to main app
                    window.location.href = '/';
                } else {
                    this.error = data.detail || 'Login failed. Please try again.';
                }
            } catch (err) {
                console.error('Login error:', err);
                this.error = 'Network error. Please check your connection.';
            } finally {
                this.loading = false;
            }
        }
    };
}

Alpine.data('loginApp', loginApp);
Alpine.start();
