
document.addEventListener("DOMContentLoaded", () => {
    const root = document.documentElement;

    // ----------------------------------
    // Theme: light / dark
    // ----------------------------------
    const themeToggle = document.getElementById("themeToggle");
    const savedTheme = localStorage.getItem("studymate-theme");

    if (savedTheme) {
        root.setAttribute("data-theme", savedTheme);
    }

    function updateThemeButton() {
        if (!themeToggle) return;

        const dark = root.getAttribute("data-theme") === "dark";
        themeToggle.textContent = dark ? "☀️" : "🌙";
        themeToggle.setAttribute(
            "aria-label",
            dark ? "Switch to light mode" : "Switch to dark mode"
        );
    }

    updateThemeButton();

    themeToggle?.addEventListener("click", () => {
        const current = root.getAttribute("data-theme");
        const next = current === "dark" ? "light" : "dark";

        root.setAttribute("data-theme", next);
        localStorage.setItem("studymate-theme", next);
        updateThemeButton();
    });

    // ----------------------------------
    // Mobile sidebar
    // ----------------------------------
    const menuToggle = document.getElementById("menuToggle");
    const sidebar = document.querySelector(".sidebar");
    const sidebarOverlay = document.getElementById("sidebarOverlay");

    function closeSidebar() {
        sidebar?.classList.remove("sidebar-open");
        sidebarOverlay?.classList.remove("active");
    }

    menuToggle?.addEventListener("click", () => {
        sidebar?.classList.toggle("sidebar-open");
        sidebarOverlay?.classList.toggle("active");
    });

    sidebarOverlay?.addEventListener("click", closeSidebar);

    sidebar?.querySelectorAll("a").forEach(link => {
        link.addEventListener("click", closeSidebar);
    });

    // ----------------------------------
    // Smooth navigation
    // ----------------------------------
    document.querySelectorAll('a[href^="#"]').forEach(link => {
        link.addEventListener("click", event => {
            const targetId = link.getAttribute("href");
            const target = document.querySelector(targetId);

            if (!target) return;

            event.preventDefault();
            target.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });
        });
    });

    // ----------------------------------
    // PDF upload feedback
    // ----------------------------------
    const uploadInput = document.getElementById("pdf");
    const fileNameDisplay = document.getElementById("fileName");
    const uploadForm = document.getElementById("uploadForm");
    const uploadButton = document.getElementById("uploadButton");

    uploadInput?.addEventListener("change", () => {
        const file = uploadInput.files?.[0];

        if (fileNameDisplay) {
            fileNameDisplay.textContent = file
                ? `Selected: ${file.name}`
                : "No file selected";
        }

        if (file && file.type !== "application/pdf") {
            alert("Please select a PDF file.");
            uploadInput.value = "";

            if (fileNameDisplay) {
                fileNameDisplay.textContent = "No file selected";
            }
        }
    });

    uploadForm?.addEventListener("submit", () => {
        const file = uploadInput?.files?.[0];

        if (!file) {
            alert("Please select a PDF file first.");
            return;
        }

        if (uploadButton) {
            uploadButton.disabled = true;
            uploadButton.textContent = "Uploading PDF...";
        }
    });

    // ----------------------------------
    // Chat input helpers
    // ----------------------------------
    const questionInput = document.getElementById("question");

    questionInput?.addEventListener("keydown", event => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();

            const askForm = document.getElementById("askForm");
            askForm?.requestSubmit();
        }
    });

    // ----------------------------------
    // Quiz selection feedback
    // ----------------------------------
    document.querySelectorAll(".quiz-option input").forEach(input => {
        input.addEventListener("change", () => {
            const group = input.closest(".quiz-options");

            group?.querySelectorAll(".quiz-option").forEach(option => {
                option.classList.remove("selected");
            });

            input.closest(".quiz-option")?.classList.add("selected");
        });
    });

    // ----------------------------------
    // Quiz generation loading state
    // ----------------------------------
    const quizForm = document.getElementById("quizForm");
    const quizButton = document.getElementById("quizButton");

    quizForm?.addEventListener("submit", () => {
        if (quizButton) {
            quizButton.disabled = true;
            quizButton.textContent = "Generating quiz...";
        }
    });

    // ----------------------------------
    // Flashcard preview interaction
    // ----------------------------------
    document.querySelectorAll(".flashcard-preview").forEach(card => {
        card.addEventListener("click", () => {
            card.classList.toggle("flipped");
        });
    });

    // ----------------------------------
    // Feedback
    // ----------------------------------
    window.sendFeedback = async function (rating) {
        const buttons = document.querySelectorAll(".feedback-button");

        buttons.forEach(button => {
            button.disabled = true;
        });

        try {
            const response = await fetch("/feedback", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    rating: rating,
                    page: window.location.pathname
                })
            });

            if (!response.ok) {
                throw new Error("Feedback request failed");
            }

            alert("Thank you for your feedback!");

        } catch (error) {
            console.error("Feedback error:", error);
            alert("We couldn't submit your feedback. Please try again.");

            buttons.forEach(button => {
                button.disabled = false;
            });
        }
    };

    window.showReportBox = function () {
        const reportBox = document.getElementById("reportBox");

        if (reportBox) {
            reportBox.hidden = !reportBox.hidden;
        }
    };

    window.sendReport = async function () {
        const reportInput = document.getElementById("reportText");
        const report = reportInput?.value.trim();

        if (!report) {
            alert("Please describe the problem first.");
            return;
        }

        try {
            const response = await fetch("/report-problem", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    report: report,
                    page: window.location.pathname
                })
            });

            if (!response.ok) {
                throw new Error("Report request failed");
            }

            alert("Thank you. Your report has been submitted.");

            reportInput.value = "";

            const reportBox = document.getElementById("reportBox");
            if (reportBox) reportBox.hidden = true;

        } catch (error) {
            console.error("Report error:", error);
            alert("We couldn't submit your report. Please try again.");
        }
    };

    // ----------------------------------
    // Scroll reveal animations
    // ----------------------------------
    const revealElements = document.querySelectorAll(
        ".reveal, .action-card, .feature-card"
    );

    if ("IntersectionObserver" in window) {
        const observer = new IntersectionObserver(
            entries => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add("visible");
                        observer.unobserve(entry.target);
                    }
                });
            },
            { threshold: 0.12 }
        );

        revealElements.forEach(element => {
            element.classList.add("reveal");
            observer.observe(element);
        });
    } else {
        revealElements.forEach(element => {
            element.classList.add("visible");
        });
    }

    console.log("StudyMate AI frontend initialized.");
});
