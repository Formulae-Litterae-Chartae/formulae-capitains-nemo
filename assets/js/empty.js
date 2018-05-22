function makePopupNote(id) {
    var popup = document.getElementById(id);
    popup.classList.toggle("show");
}

function showLemma(x) {
    var lemma = x.getAttribute("lemma");
    document.getElementById("lem_box").innerHTML = lemma;
}

function hideLemma() {
    document.getElementById("lem_box").innerHTML = "Mouse over a word to see its lemma.";
}
