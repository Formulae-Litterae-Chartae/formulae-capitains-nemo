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

//to disable cut, copy, paste, and mouse right-click
$(document).ready(function () {    
    //Disable cut, copy, and paste
    $('.no-copy').bind('cut copy paste', function (e) {
        e.preventDefault();
        $('#no-copy-message').modal('show')
    });
    
    //Disable right-mouse click
    $(".no-copy").on("contextmenu",function(e){
        return false;
    });
});

//to watermark the pdfs
//Add event listener
document.getElementById("getPdf").addEventListener("click", getPdf);

function addWaterMark(doc) {
  var totalPages = doc.internal.getNumberOfPages();

  for (i = 1; i <= totalPages; i++) {
    doc.setPage(i);
    //doc.addImage(imgData, 'PNG', 40, 40, 75, 75);
    doc.setTextColor(150);
    doc.text(50, doc.internal.pageSize.height - 30, 'Watermark');
  }

  return doc;
}
