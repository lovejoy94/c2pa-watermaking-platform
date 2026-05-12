const historyContainer =
    document.getElementById('historyContainer');

async function loadHistory(){

    try{

        const response =
            await fetch('/api/history');

        const data =
            await response.json();

        historyContainer.innerHTML = '';

        if(
            !data.analyses ||
            data.analyses.length === 0
        ){

            historyContainer.innerHTML = `
                <div class="empty">
                    Aucune analyse enregistrée.
                </div>
            `;

            return;
        }

        data.analyses.forEach(item => {

            const colorClass =
                item.score >= 80
                ? 'green'
                : item.score >= 50
                ? 'orange'
                : 'red';

            const card = document.createElement('div');

            card.className = 'history-card';

            card.innerHTML = `

                <div class="history-top">

                    <div class="file-name">
                        ${item.fichier}
                    </div>

                    <div class="score ${colorClass}">
                        ${item.score}/100
                    </div>

                </div>

                <div class="grid">

                    <div class="item">

                        <div class="item-label">
                            Type
                        </div>

                        <div class="item-value">
                            ${item.type_media}
                        </div>

                    </div>

                    <div class="item">

                        <div class="item-label">
                            C2PA
                        </div>

                        <div class="item-value">
                            ${
                                item.c2pa_certified
                                ? '✅ Certifié'
                                : '❌ Non certifié'
                            }
                        </div>

                    </div>

                    <div class="item">

                        <div class="item-label">
                            Watermark
                        </div>

                        <div class="item-value">
                            ${
                                item.watermark_found
                                ? '✅ Détecté'
                                : '⚠️ Non détecté'
                            }
                        </div>

                    </div>

                    <div class="item">

                        <div class="item-label">
                            IA
                        </div>

                        <div class="item-value">
                            ${
                                item.ai_generated
                                ? '⚠️ Détectée'
                                : '✅ Non détectée'
                            }
                        </div>

                    </div>

                    <div class="item">

                        <div class="item-label">
                            Intégrité
                        </div>

                        <div class="item-value">
                            ${
                                item.modified
                                ? '❌ Modifié'
                                : '✅ Intact'
                            }
                        </div>

                    </div>

                    <div class="item">

                        <div class="item-label">
                            Date
                        </div>

                        <div class="item-value">
                            ${item.date_analyse}
                        </div>

                    </div>

                </div>

            `;

            historyContainer.appendChild(card);

        });

    }
    catch(error){

        historyContainer.innerHTML = `
            <div class="empty">
                Erreur chargement historique.
            </div>
        `;
    }
}

loadHistory();