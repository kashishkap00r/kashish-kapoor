(function () {
    var STORAGE_KEY = "theme-storage";

    function normalizeTheme(mode) {
        return mode === "dark" ? "dark" : "light";
    }

    function getStoredTheme() {
        try {
            var storedTheme = localStorage.getItem(STORAGE_KEY);
            if (storedTheme === "dark" || storedTheme === "light") {
                return storedTheme;
            }
        } catch (e) {
            return null;
        }

        return null;
    }

    function getSystemTheme() {
        if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
            return "dark";
        }

        return "light";
    }

    function applyTheme(mode) {
        var resolvedTheme = normalizeTheme(mode);
        var htmlElement = document.documentElement;
        htmlElement.classList.remove("dark", "light");
        htmlElement.classList.add(resolvedTheme);

        var darkModeStyle = document.getElementById("darkModeStyle");
        if (darkModeStyle) {
            darkModeStyle.disabled = (resolvedTheme === "light");
        }

        var sunIcon = document.getElementById("sun-icon");
        var moonIcon = document.getElementById("moon-icon");
        if (sunIcon && moonIcon) {
            sunIcon.style.display = (resolvedTheme === "dark") ? "inline-block" : "none";
            moonIcon.style.display = (resolvedTheme === "light") ? "inline-block" : "none";
        }
    }

    function getSavedTheme() {
        return getStoredTheme() || getSystemTheme();
    }

    function setTheme(mode) {
        var resolvedTheme = normalizeTheme(mode);
        try {
            localStorage.setItem(STORAGE_KEY, resolvedTheme);
        } catch (e) {
            // Ignore storage write failures; theme still applies for this page.
        }

        applyTheme(resolvedTheme);
    }

    function toggleTheme() {
        var currentTheme = getSavedTheme();
        var nextTheme = currentTheme === "light" ? "dark" : "light";
        setTheme(nextTheme);
    }

    function updateItemToggleTheme() {
        applyTheme(getSavedTheme());
    }

    window.getSavedTheme = getSavedTheme;
    window.setTheme = setTheme;
    window.toggleTheme = toggleTheme;
    window.updateItemToggleTheme = updateItemToggleTheme;

    updateItemToggleTheme();
})();
