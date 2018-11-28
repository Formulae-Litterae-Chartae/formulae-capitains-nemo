var lexModal = document.getElementById('lexicon-modal');
var allCorporaChecks = document.querySelectorAll('input.under-all');
var formulaeChecks = document.querySelectorAll('input.under-formulae');
var chartaeChecks = document.querySelectorAll('input.under-chartae');
var placeData = document.getElementById('place-datalist');
var placeInput = document.getElementById('place-search');

$(function () {
  $('[data-toggle="popover"]').popover()
})

function makePopupNote(id) {
    var popup = document.getElementById(id);
    popup.classList.toggle("show");
}

function showLemma(x) {
    var lemma = x.getAttribute("lemma");
    var lem_box = document.getElementById("lem_box");
    lem_box.setAttribute("default-data", lem_box.innerHTML);
    lem_box.innerHTML = lemma;
}

function hideLemma() {
    var lem_box = document.getElementById("lem_box");
    lem_box.innerHTML = lem_box.getAttribute("default-data");
    lem_box.removeAttribute("default-data");
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

function hideNotes(c) {
    var nodeclass = c + ' show'
    var matches = document.getElementsByClassName(nodeclass);
    while (matches.length > 0) {
        matches.item(0).setAttribute('aria-expanded', 'false');
        matches.item(0).classList.remove('show');
    }
}

function showNotes(c) {
    var matches = document.getElementsByClassName(c);
    for (var i=0; i<matches.length; i++) {
        matches[i].classList.add('show');
        matches[i].setAttribute('aria-expanded', 'true');
    }
}

function showLexEntry(word) {
        var lemma = word.getAttribute('data-lexicon');
        var request = new XMLHttpRequest();
        var message = lexModal.getAttribute('message');
        request.onreadystatechange = function() {
            if (this.readyState == 4) {
                if (this.status == 200) {
                    lexModal.innerHTML = this.responseText;
                    lexModal.style.display = 'block';
                } else {
                    alert(message + lemma)
                }
            }
        };
        request.open('GET', '/lexicon/urn:cts:formulae:elexicon.' + lemma + '.deu001', true);
        request.send()
    }

function closeLexEntry() {
    lexModal.style.display = "none";
}
    
window.onclick = function(event) {
    if (event.target == lexModal) {
        lexModal.style.display = 'none';
    }
}

// Thanks to https://stackoverflow.com/questions/31136882/displaying-slider-value-alongside-wtforms-fields-html5-decimalrangefield
function outputUpdate(plusMinus, targetId) {
    document.querySelector(targetId).value = plusMinus;
}

function checkSubCorpora(tag, category) {
    var subelements = document.getElementsByClassName(category)
    for(var i=0; i<subelements.length; i++) {
        subelements[i].checked = tag.checked;
    }
}

function getSubElements(coll) {
        var objectId = coll.getAttribute('sub-element-url');
        var targetList = document.getElementById(coll.getAttribute('sub-element-id'));
        if (coll.getAttribute('ul-shown') == 'true') {
            coll.setAttribute('ul-shown', 'false');
            targetList.innerHTML = ''
        } else {
            var request = new XMLHttpRequest();
            request.onreadystatechange = function() {
                if (this.readyState == 4) {
                    if (this.status == 200) {
                        targetList.innerHTML = this.responseText;
                        coll.setAttribute('ul-shown', 'true');
                    } else {
                        alert("No texts found for collection.")
                    }
                }
            };
            request.open('GET', objectId, true);
            request.send()
    }
}

// for autocomplete as you type I need the following things:
// - a listener for when the field changes
// $('#place-search').on("focus", function() {
//        var word = $(this).val();
//        if(word !== ''){
//            previous = word;
//            suggestion();
//        }
// });
// - a function that sends the partial search query request to the server to be sent to elasticsearch (see showLexEntry above)
// this is taken directly from https://blog.teamtreehouse.com/creating-autocomplete-dropdowns-datalist-element
// function suggestion(){
//     var request = new XMLHttpRequest();
//     
//     request.onreadystatechange = function(response) {
//         if (request.readyState === 4) {
//             if (request.status === 200) {
//                 var jsonOptions = JSON.parse(request.responseText);
//                 
//                 jsonOptions.forEach(function(item) {
//                     var option = document.createElement('option');
//                     option.value = item;
//                     placeData.appendChild(option);
//                 });
//             placeInput.placeholder = placeInput.getAttribute('default');
//             } else {
//                 // An error occured
//                 placeInput.placeholder = "Couldn't load places.";
//             }
//         }
//     }
//     
//     placeInput.placeholder = "Loading options...";
//     
//     // Set up and make the request.
//     request.open('GET', '/search/suggest/word', true);
//     request.send();
// };
// - something that adds the returned results to something (a dropdown menu?) from which the user can choose an element which will fill the search query box
// see https://blog.manifold.co/leveraging-the-power-of-elasticsearch-autocomplete-and-fuzzy-search-1d491d3e0b38 for some ideas
