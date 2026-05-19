const params = new URLSearchParams(window.location.search);

const fichier         = params.get('fichier') || 'Fichier inconnu';
const typeMedia       = params.get('type_media') || 'inconnu';

const score           = parseInt(params.get('score')) || 0;

const label           = params.get('label') || '—';

const certified       = params.get('c2pa_certified') === 'true';

const hasManifest     = params.get('has_manifest') === 'true';

const watermark       = params.get('watermark_found') === 'true';

const aiGenerated     = params.get('ai_generated') === 'true';

const modified        = params.get('modified') === 'true';

const sha256          = params.get('sha256') || '—';

const toolUsed = params.get('tool_used') || 'Inconnu'; 

const date            = params.get('date_analyse')
                        || new Date().toLocaleString();

const icons = {
    image:'🖼️',
    video:'🎬',
    audio:'🎵'
};
document.getElementById('toolUsedVal').textContent = toolUsed;
document.getElementById('fileIcon').textContent =
    icons[typeMedia] || '📄';

document.getElementById('fileName').textContent =
    fichier;

document.getElementById('fileMeta').textContent =
    `Type : ${typeMedia}`;

const color =
    score >= 80
    ? 'var(--green)'
    : score >= 50
    ? 'var(--orange)'
    : 'var(--red)';

const emoji =
    score >= 80
    ? '✅'
    : score >= 50
    ? '⚠️'
    : '❌';

document.getElementById('scoreValue').textContent =
    `${score}%`;

document.getElementById('scoreValue').style.color =
    color;

document.getElementById('scoreMessage').textContent =
    `${emoji} ${label}`;

document.getElementById('scoreMessage').style.color =
    color;

setTimeout(() => {

    document.getElementById('scoreBar').style.width =
        `${score}%`;

    document.getElementById('scoreBar').style.background =
        color;

},100);

function boolVal(
    id,
    val,
    trueText,
    falseText,
    trueClass,
    falseClass
){
    const el = document.getElementById(id);

    el.textContent =
        val ? trueText : falseText;

    el.className =
        `value ${val ? trueClass : falseClass}`;
}

boolVal(
    'certifiedVal',
    certified,
    '✅ Certifié',
    '❌ Non certifié',
    'ok',
    'bad'
);

boolVal(
    'manifestVal',
    hasManifest,
    '✅ Présent',
    '❌ Absent',
    'ok',
    'bad'
);

boolVal(
    'watermarkVal',
    watermark,
    '✅ Détecté',
    '⚠️ Non détecté',
    'ok',
    'warn'
);

boolVal(
    'aiVal',
    aiGenerated,
    '⚠️ Détectée',
    '✅ Non détectée',
    'warn',
    'ok'
);

boolVal(
    'modifiedVal',
    modified,
    '❌ Modifié',
    '✅ Intact',
    'bad',
    'ok'
);

document.getElementById('dateVal').textContent =
    date;

document.getElementById('sha256Val').textContent =
    sha256;
    