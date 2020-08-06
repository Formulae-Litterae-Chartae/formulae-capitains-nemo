var allCorporaChecks = document.querySelectorAll('input.under-all');
var formulaeChecks = document.querySelectorAll('input.under-formulae');
var chartaeChecks = document.querySelectorAll('input.under-chartae');
var wordSearchData = document.getElementById('word-search-datalist');
var wordSearchInput = document.getElementById('word-search-box');
var regestSearchData = document.getElementById('regest-word-search-datalist');
var regestSearchInput = document.getElementById('regest-word-search-box');
var textSearchTimeout = null;
var searchLemmas = document.getElementById('lemma_search');
var firstLetter = document.getElementById('firstLetter');
var specialDays = document.querySelectorAll('input[name="special_days"]');
var datePlusMinusInput = document.getElementById('date_plus_minus');
var slopInput = document.getElementById('slop');

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

// for autocomplete as you type I need the following things:
// - a listener for when the field changes
// see https://blog.manifold.co/leveraging-the-power-of-elasticsearch-autocomplete-and-fuzzy-search-1d491d3e0b38 for some ideas
wordSearchInput.onkeyup = function(e) {
    sendAutocompleteRequest(wordSearchInput, wordSearchData, "text");
}

regestSearchInput.onkeyup = function(e) {
    sendAutocompleteRequest(regestSearchInput, regestSearchData, "regest");
}

function sendAutocompleteRequest(sourceElement, targetElement, qSource) {
    // using the timeout so that it waits until the user stops typing for .5 seconds before making the request to the server
    // idea from https://schier.co/blog/2014/12/08/wait-for-user-to-stop-typing-using-javascript.html
    clearTimeout(textSearchTimeout);
    var subdomain = '';
    if (window.location.host == 'tools.formulae.uni-hamburg.de') {
        subdomain = '/dev'
    }
    textSearchTimeout = setTimeout(function () {
        // - a function that sends the partial search query request to the server to be sent to elasticsearch (see showLexEntry above)
        // this is taken directly from https://blog.teamtreehouse.com/creating-autocomplete-dropdowns-datalist-element
        var word = sourceElement.value;
        if(word !== '' && !(word.match(/[\*\?]/))){
            previous = word;
            var request = new XMLHttpRequest();
            request.onreadystatechange = function(response) {
                if (request.readyState === 4) {
                    if (request.status === 200) {
                        var jsonOptions = JSON.parse(request.responseText);
                        var docFrag = document.createDocumentFragment();
                        jsonOptions.forEach(function(item) {
                            var option = document.createElement('option');
                            option.value = item;
                            docFrag.appendChild(option);
                        });
                        targetElement.innerHTML = '';
                        targetElement.appendChild(docFrag);
                        sourceElement.placeholder = sourceElement.getAttribute('default');
                    } else {
                        // An error occured
                        sourceElement.placeholder = "Couldn't load suggestions.";
                    }
                }
            };
            
            sourceElement.placeholder = "Loading options...";
            
            // Set up and make the request.
            request.open('GET', subdomain + '/search/suggest/' + word + buildUrl(qSource), true);
            request.send();
        }
    }, 500);
};

// *******************************************************************
// functions to store unsubmitted values from the advanced search page
// *******************************************************************

// build the tail end of the url to submit via AJAX
function buildUrl(qSource) {
    var params = {
        corpus:[],
        lemma_search:'autocomplete',
        fuzziness:'0',
        in_order:'False',
        year:'0',
        slop:'0',
        month:'0',
        day:'0',
        year_start:'0',
        month_start:'0',
        day_start:'0',
        year_end:'0',
        month_end:'0',
        day_end:'0',
        date_plus_minus:'0',
        exclusive_date_range:'False',
        composition_place:'',
        special_days:[],
        regest_field:'regest'
    };
    if (qSource == "text") {
        params.extra_q = document.getElementById('regest-word-search-box').value;
        var extraField = 'regest_q';
        if (searchLemmas.checked) {
            params.lemma_search = 'autocomplete_lemmas';
        } else {
            params.lemma_search = 'autocompslopInputlete';
        }
    } else if (qSource == "regest") {
        params.extra_q = document.getElementById('word-search-box').value;
        params.regest_field = 'autocomplete_regest';
        var extraField = 'q';
        if (searchLemmas.checked) {
            params.lemma_search = 'True';
        } else {
            params.lemma_search = 'False';
        }
    }
    formulaeChecks.forEach(function(formula) {
        if (formula.checked) {
            params.corpus.push(formula.value);
        }
    });
    chartaeChecks.forEach(function(charter) {
        if (charter.checked) {
            params.corpus.push(charter.value);
        }
    });
    specialDays.forEach(function(day) {
        if (day.checked) {
            params.special_days.push(day.value);
        }
    });
    if (document.getElementById('in_order').checked) {
        params.in_order = document.getElementById('in_order').value;
    };
    // Transfer the other values from the form to params
    var advancedForm = document.getElementById('advanced-form');
    for (f of advancedForm) {
        if (f.name && !(['corpus', 'special_days', 'in_order', 'regest_field', 'lemma_search'].includes(f.name)) && params[f.name]) {
            params[f.name] = f.value;
        }
    }
    // Build the URL extension
    var brandNewUrl = "?";
    for (f in params) {
        if (f != 'extra_field' && f != 'extra_q') {
            brandNewUrl += f + '=' + params[f] + '&';
        }
    }
    brandNewUrl += extraField + "=" + params.extra_q + '&qSource=' + qSource;
    return brandNewUrl;
}

function change_lemma_search() {
    searchLemmas = !searchLemmas;
}

function updateParam(par) {
    if (par === 'searchLemmas') {
        params.field = this.val();
    } else {
        params[par] = this.value;
    }
}

// autocomplete for the Issued At search using JQuery UI
$( "#place-search" ).autocomplete({
    source: function( request, response ) {
        if ( firstLetter.checked ) {
            var matcher = new RegExp( "^" + $.ui.autocomplete.escapeRegex( request.term ), "i" );
            response( $.grep( tags, function( item ){
                return matcher.test( item );
            }) );document.getElementById('advancedResetButton').addEventListener("click", resetAdvancedSearchForm);
    } else {
        var matcher = new RegExp( $.ui.autocomplete.escapeRegex( request.term ), "i" );
        response( $.grep( tags, function( item ){
            return matcher.test( item );
        }) );
    }
    }
});

datePlusMinusInput.addEventListener('input', function () {
    datePlusMinusInput.setCustomValidity("");
    datePlusMinusInput.checkValidity();
});

datePlusMinusInput.addEventListener('invalid', function () {
    datePlusMinusInput.setCustomValidity(datePlusMinusInvalidMessage);
});

slopInput.addEventListener('input', function () {
    slopInput.setCustomValidity("");
    slopInput.checkValidity();
});

slopInput.addEventListener('invalid', function () {
    slopInput.setCustomValidity(slopInvalidMessage);
});

document.getElementById('advancedResetButton').addEventListener("click", function () {
    document.getElementById('advanced-form').reset();
}
