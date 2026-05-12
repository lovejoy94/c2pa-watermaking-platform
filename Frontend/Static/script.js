const uploadZone = document.getElementById("uploadZone");

const fileInput = document.getElementById("fileInput");

const importBtn = document.getElementById("importBtn");

const analyzeBtn = document.getElementById("analyzeBtn");

const fileInfo = document.getElementById("fileInfo");

const loader = document.getElementById("loader");

const resultBox = document.getElementById("resultBox");

analyzeBtn.style.display = "none";

loader.style.display = "none";

/* ======================================================= */
/* CHOIX FICHIER */
/* ======================================================= */

importBtn.addEventListener("click", () => {

    fileInput.click();
});

uploadZone.addEventListener("click", () => {

    fileInput.click();
});

fileInput.addEventListener("change", () => {

    afficherFichier();
});

/* ======================================================= */
/* DRAG & DROP */
/* ======================================================= */

uploadZone.addEventListener("dragover", (event) => {

    event.preventDefault();

    uploadZone.classList.add("dragover");
});

uploadZone.addEventListener("dragleave", () => {

    uploadZone.classList.remove("dragover");
});

uploadZone.addEventListener("drop", (event) => {

    event.preventDefault();

    uploadZone.classList.remove("dragover");

    if (event.dataTransfer.files.length > 0) {

        fileInput.files = event.dataTransfer.files;

        afficherFichier();
    }
});

/* ======================================================= */
/* AFFICHAGE FICHIER */
/* ======================================================= */

function afficherFichier() {

    const file = fileInput.files[0];

    if (file) {

        fileInfo.textContent =
            `✅ ${file.name} (${(file.size / 1024).toFixed(1)} Ko)`;

        analyzeBtn.style.display = "inline-flex";
    }
}

/* ======================================================= */
/* ANALYSE */
/* ======================================================= */

analyzeBtn.addEventListener("click", async () => {

    const file = fileInput.files[0];

    if (!file) {

        alert("Veuillez choisir un fichier.");

        return;
    }

    const formData = new FormData();

    formData.append("media", file);

    loader.style.display = "flex";

    resultBox.innerHTML = "";

    try {

        const response = await fetch("/analyze", {

            method: "POST",

            body: formData
        });

        const data = await response.json();

        loader.style.display = "none";

        resultBox.innerHTML = `
            <div class="result">
                <h3>Résultat</h3>

                <p><strong>Fichier :</strong> ${data.fichier}</p>

                <p><strong>Score :</strong> ${data.score.score}/100</p>

                <p><strong>Niveau :</strong> ${data.score.label}</p>
            </div>
        `;

    } catch (error) {

        loader.style.display = "none";

        resultBox.innerHTML = `
            <div class="result error">
                ❌ Erreur serveur
            </div>
        `;
    }
});