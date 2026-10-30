document.addEventListener("DOMContentLoaded", () => {
    const root = document.documentElement;

    // Theme toggle
    const themeToggle = document.getElementById("theme-toggle");
    const savedTheme = localStorage.getItem("studymate-theme");

    if (savedTheme === "light" || savedTheme === "dark") {
        root.setAttribute("data-theme", savedTheme);
    }

    function updateThemeButton() {
        if (!themeToggle) return;
        const isDark = root.getAttribute("data-theme") === "dark";
        themeToggle.innerHTML = isDark
            ? '<i class="fa-regular fa-sun" aria-hidden="true"></i>'
            : '<i class="fa-regular fa-moon" aria-hidden="true"></i>';
        themeToggle.setAttribute(
            "aria-label",
            isDark ? "Switch to light mode" : "Switch to dark mode"
        );
    }

    updateThemeButton();

    themeToggle?.addEventListener("click", () => {
        const nextTheme =
            root.getAttribute("data-theme") === "dark" ? "light" : "dark";
        root.setAttribute("data-theme", nextTheme);
        localStorage.setItem("studymate-theme", nextTheme);
        updateThemeButton();
    });

    // Mobile sidebar — selectors match the recovered HTML and CSS.
    const menuToggle = document.getElementById("mobile-menu");
    const sidebar = document.getElementById("sidebar");

    function closeSidebar() {
        sidebar?.classList.remove("open");
        menuToggle?.setAttribute("aria-expanded", "false");
    }

    menuToggle?.setAttribute("aria-expanded", "false");
    menuToggle?.addEventListener("click", () => {
        const isOpen = sidebar?.classList.toggle("open") ?? false;
        menuToggle.setAttribute("aria-expanded", String(isOpen));
    });

    sidebar?.querySelectorAll("a").forEach(link => {
        link.addEventListener("click", closeSidebar);
    });

    document.addEventListener("keydown", event => {
        if (event.key === "Escape") closeSidebar();
    });

    // Smooth in-page navigation.
    document.querySelectorAll('a[href^="#"]').forEach(link => {
        link.addEventListener("click", event => {
            const target = document.querySelector(link.getAttribute("href"));
            if (!target) return;
            event.preventDefault();
            target.scrollIntoView({ behavior: "smooth", block: "start" });
        });
    });

    // PDF upload feedback and client-side validation.
    const uploadInput = document.getElementById("pdf-file");
    const fileNameDisplay = document.getElementById("file-name");
    const uploadForm = document.getElementById("upload-form");
    const uploadButton = uploadForm?.querySelector('button[type="submit"]');

    uploadInput?.addEventListener("change", () => {
        const file = uploadInput.files?.[0];

        if (fileNameDisplay) {
            fileNameDisplay.textContent = file
                ? `Selected: ${file.name}`
                : "No file selected";
        }

        if (!file) return;

        const isPdf =
            file.type === "application/pdf" ||
            file.name.toLowerCase().endsWith(".pdf");

        if (!isPdf) {
            alert("Please select a PDF file.");
            uploadInput.value = "";
            if (fileNameDisplay) fileNameDisplay.textContent = "No file selected";
            return;
        }

        if (file.size > 20 * 1024 * 1024) {
            alert("Please choose a PDF smaller than 20 MB.");
            uploadInput.value = "";
            if (fileNameDisplay) fileNameDisplay.textContent = "No file selected";
        }
    });

    uploadForm?.addEventListener("submit", event => {
        const file = uploadInput?.files?.[0];
        if (!file) {
            event.preventDefault();
            alert("Please choose a PDF first.");
            return;
        }

        if (uploadButton) {
            uploadButton.disabled = true;
            uploadButton.innerHTML =
                '<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i> Uploading…';
        }
    });

    // Submit the tutor question with Enter.
    const questionInput = document.getElementById("question");
    const chatForm = document.getElementById("chat-form");

    questionInput?.addEventListener("keydown", event => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            chatForm?.requestSubmit();
        }
    });

    // Quiz option selection and generation state.
    document.querySelectorAll(".question-options input[type='radio']").forEach(input => {
        input.addEventListener("change", () => {
            const group = input.closest(".question-options");
            group?.querySelectorAll(".option").forEach(option => {
                option.classList.remove("selected");
            });
            input.closest(".option")?.classList.add("selected");
        });
    });

    const quizForm = document.getElementById("quiz-form");
    const quizButton = quizForm?.querySelector('button[type="submit"]');

    quizForm?.addEventListener("submit", () => {
        if (quizButton) {
            quizButton.disabled = true;
            quizButton.textContent = "Generating quiz…";
        }
    });

    // Feedback API: use the field names and endpoint implemented by Flask.
    const feedbackMessage = document.getElementById("feedback-message");
    const reportBox = document.getElementById("report-box");
    const reportInput = document.getElementById("report-input");

    function showFeedbackMessage(message, isError = false) {
        if (!feedbackMessage) return;
        feedbackMessage.textContent = message;
        feedbackMessage.classList.toggle("error", isError);
        feedbackMessage.setAttribute("role", "status");
    }

    window.sendFeedback = async function (feedbackType, button) {
        const buttons = document.querySelectorAll(".feedback-btn");
        buttons.forEach(item => { item.disabled = true; });

        try {
            const response = await fetch("/feedback", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    feedback_type: feedbackType,
                    details: ""
                })
            });
            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.message || "Feedback could not be saved.");
            }

            showFeedbackMessage(data.message || "Thank you for your feedback.");
            if (button) button.classList.add("selected");
        } catch (error) {
            console.error("StudyMate feedback error:", error);
            showFeedbackMessage(
                error.message || "We couldn't submit your feedback. Please try again.",
                true
            );
            buttons.forEach(item => { item.disabled = false; });
        }
    };

    window.showReportBox = function () {
        if (!reportBox) return;
        const isOpen = reportBox.classList.toggle("is-open");
        if (isOpen) reportInput?.focus();
    };

    window.sendReport = async function () {
        const details = reportInput?.value.trim();
        if (!details) {
            showFeedbackMessage("Please describe the problem first.", true);
            reportInput?.focus();
            return;
        }

        const reportButton = reportBox?.querySelector("button");
        if (reportButton) reportButton.disabled = true;

        try {
            const response = await fetch("/feedback", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    feedback_type: "report",
                    details
                })
            });
            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.message || "Your report could not be saved.");
            }

            showFeedbackMessage(data.message || "Thank you for your report.");
            if (reportInput) reportInput.value = "";
            reportBox?.classList.remove("is-open");
        } catch (error) {
            console.error("StudyMate report error:", error);
            showFeedbackMessage(
                error.message || "We couldn't submit your report. Please try again.",
                true
            );
        } finally {
            if (reportButton) reportButton.disabled = false;
        }
    };

    // Reveal elements as they enter the viewport.
    const revealElements = document.querySelectorAll(
        ".action-card, .tool-card, .upload-panel, .chat-panel"
    );

    if ("IntersectionObserver" in window) {
        const observer = new IntersectionObserver(entries => {
            entries.forEach(entry => {
                if (!entry.isIntersecting) return;
                entry.target.classList.add("visible");
                observer.unobserve(entry.target);
            });
        }, { threshold: 0.12 });

        revealElements.forEach(element => observer.observe(element));
    } else {
        revealElements.forEach(element => element.classList.add("visible"));
    }

    console.info("StudyMate AI frontend initialized.");
});
