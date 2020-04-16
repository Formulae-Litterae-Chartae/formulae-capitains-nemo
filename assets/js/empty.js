$(function () {
  $('[data-toggle="popover"]').popover()
})
  
function restrictSearch() {
    var button = document.getElementById('restrictSearchButton');
    var re = new RegExp('&corpus=[^&]*');
    var corpora = document.getElementsByClassName('corp-restrict-to');
    var oldUrl = button.getAttribute('href');
    var newCorpora = new Array();
    for (let corp of corpora){
        if (corp.checked) {
            newCorpora.push(corp.getAttribute('value'));
        }
    }
    button.setAttribute('href', oldUrl.replace(re, '&corpus=' + newCorpora.join('%2B') + '&old_search=True'));
}

function makeLemmaSearch() {
    var button = document.getElementById('lemmaSearchButton');
    var reQ = new RegExp('&q=[^&]*');
    var reField = new RegExp('&lemma_search=[^&]*');
    var rePage = new RegExp('&page=[^&]*');
    var lemmas = document.getElementsByClassName('lem-to-search');
    var oldUrl = button.getAttribute('href');
    var newQ = new Array();
    for (let lemma of lemmas){
        if (lemma.checked || lemma.getAttribute('checked') == 'True') {
            newQ.push(lemma.getAttribute('value'));
        }
    };
    oldUrl = oldUrl.replace(reField, '');
    oldUrl = oldUrl.replace(rePage, '');
    button.setAttribute('href', oldUrl.replace(reQ, '&q=' + newQ.join('+')) + '&lemma_search=True');
}


// I think this function was for when I was using the accordion to expand a collection to its works on the collection screen.
// I don't think it is needed any more so I am commenting it out and testing, just to make sure.
// function getSubElements(coll) {
//         var objectId = coll.getAttribute('sub-element-url');
//         var targetList = document.getElementById(coll.getAttribute('sub-element-id'));
//         if (coll.getAttribute('ul-shown') == 'true') {
//             coll.setAttribute('ul-shown', 'false');
//             targetList.innerHTML = ''
//         } else {
//             var request = new XMLHttpRequest();
//             request.onreadystatechange = function() {
//                 if (this.readyState == 4) {
//                     if (this.status == 200) {
//                         targetList.innerHTML = this.responseText;
//                         coll.setAttribute('ul-shown', 'true');
//                     } else {
//                         alert("No texts found for collection.")
//                     }
//                 }
//             };
//             request.open('GET', objectId, true);
//             request.send()
//     }
// }

// AJAX request to change locale and then refresh the page
$('.lang-link').bind('click', function(event) {
    event.preventDefault();
    e = this;
    var subdomain = '';
    if (window.location.host == 'tools.formulae.uni-hamburg.de') {
        subdomain = '/dev'
    }
    var request = new XMLHttpRequest();
    request.onreadystatechange = function() {
        if (this.readyState == 4) {
            if (this.status == 200) {
                location.reload();
            } else {
                alert('Failed to change language')
            }
        }
    };
    request.open('GET', subdomain + '/lang/' + e.getAttribute('value'), true);
    request.setRequestHeader("X-Requested-With", "XMLHttpRequest");
    request.send()
})

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
    
    var parLinks = document.getElementsByClassName('paragraph-link');
    for (let link of parLinks) {
        if (document.getElementById(link.getAttribute('link-to'))) {
            link.removeAttribute('hidden');
        }
    }
    
});
