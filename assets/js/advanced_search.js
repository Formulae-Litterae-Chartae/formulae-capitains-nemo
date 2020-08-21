var textSearchTimeout = null;
var searchLemmas = document.getElementById('lemma_search');

// Thanks to https://stackoverflow.com/questions/31136882/displaying-slider-value-alongside-wtforms-fields-html5-decimalrangefield
function outputUpdate(plusMinus, targetId) {
    document.querySelector(targetId).value = plusMinus;
}

function checkSubCorpora(tag, category) {
    var subelements = document.getElementsByClassName(category);
    var l = subelements.length;
    var i;
    for(i = 0; i < l; i++) {
        subelements[i].checked = tag.checked;
    }
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
        var word = sourceElement.val();
        if(word !== '' && !(word.match(/[\*\?]/))){
            previous = word;
            var request = $.ajax( subdomain + '/search/suggest/' + word + buildUrl(qSource) )
                .done(function (response, status) {
                    var jsonOptions = JSON.parse(response);
                    var docFrag = document.createDocumentFragment();
                    jsonOptions.forEach(function(item) {
                        var option = document.createElement('option');
                        option.value = item;
                        docFrag.appendChild(option);
                    });
                    targetElement.html('');
                    targetElement.append(docFrag);
                    sourceElement.placeholder = sourceElement.attr('default');
                    })
                .fail(function () {
                        // An error occured
                        sourceElement.placeholder = "Couldn't load suggestions.";
                    })
            
            sourceElement.placeholder = "Loading options...";
        }
    }, 500)
}

// *******************************************************************
// functions to store unsubmitted values from the advanced search page
// *******************************************************************

// build the tail end of the url to submit via AJAX
function buildUrl(qSource) {
    var corpus = [];
    var special_days = [];
    var params = {
        corpus:'',
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
        special_days:'',
        regest_field:'regest'
    };
    if (qSource == "text") {
        params.extra_q = document.getElementById('regest-word-search-box').value;
        var extraField = 'regest_q';
        if (searchLemmas.checked) {
            params.lemma_search = 'autocomplete_lemmas';
        } else {
            params.lemma_search = 'autocomplete';
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
    $('input.under-formulae').each(function(i, formula) {
        if (formula.checked) {
            corpus.push(formula.value);
        }
    })
    $('input.under-chartae').each(function(i, charter) {
        if (charter.checked) {
            corpus.push(charter.value);
        }
    })
    $('input[name="special_days"]').each(function(i, day) {
        if (day.checked) {
            special_days.push(day.value);
        }
    })
    if (document.getElementById('in_order').checked) {
        params.in_order = document.getElementById('in_order').value;
    }
    params.corpus = corpus.join('+');
    params.special_days = special_days.join('+');
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
        params.field = this.value;
    } else {
        params[par] = this.value;
    }
}

$(document).ready(function () {
    // autocomplete for the Issued At search using JQuery UI
    $( "#place-search" ).autocomplete({
        source: function( request, response ) {
            if ( document.getElementById('firstLetter').checked ) {
                var matcher = new RegExp( "^" + $.ui.autocomplete.escapeRegex( request.term ), "i" );
                response( $.grep( tags, function( item ){
                    return matcher.test( item );
                }) );
            } else {
                var matcher = new RegExp( $.ui.autocomplete.escapeRegex( request.term ), "i" );
                response( $.grep( tags, function( item ){
                    return matcher.test( item );
                }) );
            }
        }
    })

    // for autocomplete as you type I need the following things:
    // - a listener for when the field changes
    // see https://blog.manifold.co/leveraging-the-power-of-elasticsearch-autocomplete-and-fuzzy-search-1d491d3e0b38 for some ideas
    $('#word-search-box').keyup(function(e) {
        sendAutocompleteRequest($( this ), $('#word-search-datalist'), "text");
    });

    $('#regest-word-search-box').keyup(function(e) {
        sendAutocompleteRequest($( this ), $('#regest-word-search-datalist'), "regest");
    });
     
    var datePlusMinusInput = document.getElementById('date_plus_minus');
    var slopInput = document.getElementById('slop');

    datePlusMinusInput.addEventListener('input', function () {
        datePlusMinusInput.setCustomValidity("");
        datePlusMinusInput.checkValidity();
    })

    datePlusMinusInput.addEventListener('invalid', function () {
        datePlusMinusInput.setCustomValidity(datePlusMinusInvalidMessage);
    })

    slopInput.addEventListener('input', function () {
        slopInput.setCustomValidity("");
        slopInput.checkValidity();
    })

    slopInput.addEventListener('invalid', function () {
        slopInput.setCustomValidity(slopInvalidMessage);
    })

    $('#advancedResetButton').click(function () {
        document.getElementById('advanced-form').reset();
    })
})
