// =========================
// script.js
// =========================

// MENU HAMBURGER

const hamburger = document.getElementById("hamburger");
const navMenu = document.getElementById("nav-menu");

if(hamburger){
    hamburger.addEventListener("click", () => {
        navMenu.classList.toggle("active");
    });
}

// IMPORT FICHIER

const importBtn = document.getElementById("importBtn");
const fileInput = document.getElementById("fileInput");
const fileInfo = document.getElementById("fileInfo");
const analyzeBtn = document.getElementById("analyzeBtn");
const loader = document.getElementById("loader");

if(importBtn){

    importBtn.addEventListener("click", () => {
        fileInput.click();
    });

    fileInput.addEventListener("change", () => {

        const file = fileInput.files[0];

        if(file){

            fileInfo.innerHTML = `
                <p><strong>Fichier :</strong> ${file.name}</p>
                <p><strong>Taille :</strong> ${(file.size/1024).toFixed(2)} KB</p>
            `;

            analyzeBtn.style.display = "inline-block";
        }

    });

}

// ANALYSE

if(analyzeBtn){

    analyzeBtn.addEventListener("click", () => {

        loader.style.display = "block";

        setTimeout(() => {

            loader.style.display = "none";

            window.location.href = "results.html";

        }, 3000);

    });

}