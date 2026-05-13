function toggleMenu(){

    const sidebar =
    document.getElementById("sidebar");

    if(sidebar.style.left === "0px"){

        sidebar.style.left = "-250px";

    }else{

        sidebar.style.left = "0px";
    }
}
const importBtn = document.getElementById('importBtn');
const fileInput = document.getElementById('fileInput');
const fileInfo = document.getElementById('fileInfo');

// Au clic sur le bouton, on déclenche l'input file
importBtn.addEventListener('click', () => {
    fileInput.click();
});

// Quand un fichier est sélectionné
fileInput.addEventListener('change', (event) => {
    const file = event.target.files[0];
    if (file) {
        fileInfo.innerHTML = `✅ Fichier sélectionné : ${file.name} (${(file.size / 1024).toFixed(1)} Ko)`;
        // Vous pouvez ajouter ici un appel à une fonction pour prévisualiser ou envoyer
    } else {
        fileInfo.innerHTML = '';
    }
});
// Sélection des éléments
const analyzeBtn = document.getElementById('analyzeBtn');
const loader = document.getElementById('loader');
const importBtn = document.getElementById('importBtn');
let selectedFile = null;

// Modifier le fileInput change pour stocker le fichier et afficher le bouton Analyser
fileInput.addEventListener('change', (event) => {
    selectedFile = event.target.files[0];
    if (selectedFile) {
        fileInfo.style.display = 'block';
        fileInfo.innerHTML = `
            ✅ Fichier sélectionné : <strong>${selectedFile.name}</strong><br>
            📦 Taille : ${(selectedFile.size / 1024).toFixed(1)} Ko<br>
            📁 Type : ${selectedFile.type || 'inconnu'}
        `;
        importBtn.textContent = '📤 Changer de fichier';
        
        // AFFICHER LE BOUTON ANALYSER
        analyzeBtn.style.display = 'inline-block';
    } else {
        fileInfo.style.display = 'none';
        analyzeBtn.style.display = 'none';
    }
});

// Fonction d'analyse avec temps de réflexion + redirection
analyzeBtn.addEventListener('click', async () => {
    if (!selectedFile) {
        alert('Veuillez d\'abord sélectionner un fichier.');
        return;
    }
    
    // 1. Cacher le bouton Analyser et afficher le loader
    analyzeBtn.style.display = 'none';
    importBtn.disabled = true;
    loader.style.display = 'block';
    
    // 2. Simulation d'un temps de réflexion (analyse)
    //    Dans la réalité, vous enverriez le fichier à un serveur Flask
    await new Promise(resolve => setTimeout(resolve, 2000)); // 2 secondes
    
    // 3. Calculer un score d'authenticité simulé (entre 0 et 100)
    //    Vous pouvez remplacer ceci par une vraie analyse
    const fakeScore = Math.floor(Math.random() * (95 - 30 + 1) + 30);
    
    // 4. Rediriger vers la page résultat avec les paramètres
    const params = new URLSearchParams({
        name: selectedFile.name,
        size: selectedFile.size,
        type: selectedFile.type || 'application/octet-stream',
        score: fakeScore,
        timestamp: Date.now()
    });
    
    // Redirection vers resultat.html avec les paramètres
    window.location.href = `resultat.html?${params.toString()}`;
});