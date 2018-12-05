var allCorporaChecks = document.querySelectorAll('input.under-all');
var formulaeChecks = document.querySelectorAll('input.under-formulae');
var chartaeChecks = document.querySelectorAll('input.under-chartae');
var wordSearchData = document.getElementById('word-search-datalist');
var wordSearchInput = document.getElementById('word-search-box');
var textSearchTimeout = null;
var searchLemmas = false;

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
    // using the timeout so that it waits until the user stops typing for .5 seconds before making the request to the server
    // idea from https://schier.co/blog/2014/12/08/wait-for-user-to-stop-typing-using-javascript.html
    clearTimeout(textSearchTimeout);
    textSearchTimeout = setTimeout(function () {
        // - a function that sends the partial search query request to the server to be sent to elasticsearch (see showLexEntry above)
        // this is taken directly from https://blog.teamtreehouse.com/creating-autocomplete-dropdowns-datalist-element
        var word = wordSearchInput.value;
        if(word !== ''){
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
                        wordSearchData.innerHTML = '';
                        wordSearchData.appendChild(docFrag);
                        wordSearchInput.placeholder = wordSearchInput.getAttribute('default');
                    } else {
                        // An error occured
                        wordSearchInput.placeholder = "Couldn't load suggestions.";
                    }
                }
            };
            
            wordSearchInput.placeholder = "Loading options...";
            
            // Set up and make the request.
            request.open('GET', '/search/suggest/' + word + buildUrl(), true);
            request.send();
        }
    }, 500);
};

// *******************************************************************
// functions to store unsubmitted values from the advanced search page
// *******************************************************************

// build the tail end of the url to submit via AJAX
function buildUrl() {
    var corpus = 'all';
    var field = 'autocomplete';
    var fuzziness = '0';
    var in_order = 'False';
    var year = '0';
    var slop = '0';
    var month = '0';
    var day = '0';
    var year_start = '0';
    var month_start = '0';
    var day_start = '0';
    var year_end = '0';
    var month_end = '0';
    var day_end = '0';
    var date_plus_minus = '0';
    var exclusive_date_range = 'False';
    var composition_place= '';
    if (searchLemmas === true) {
        field = 'autocomplete_lemmas';
    }
    var urlExt = "?corpus=" + corpus + "&field=" + field + "&fuzziness=" + fuzziness + "&in_order=" + in_order + "&year=" + year + "&slop=" + slop + "&month=" + month + "&day=" + day + "&year_start=" + year_start + "&month_start=" + month_start + "&day_start=" + day_start + "&year_end=" + year_end + "&month_end=" + month_end + "&day_end=" + day_end + "&date_plus_minus=" + date_plus_minus + "&exclusive_date_range=" + exclusive_date_range + "&composition_place=" + composition_place;
    return urlExt;
}

function change_lemma_search() {
    searchLemmas = !searchLemmas;
}
