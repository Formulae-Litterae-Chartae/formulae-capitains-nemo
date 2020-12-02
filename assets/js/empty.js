var subdomain = '';
if (window.location.host == 'tools.formulae.uni-hamburg.de') {
    subdomain = '/dev'
}
var textSearchTimeout = null;
var searchLemmas = document.getElementById('lemma_search');


// This is to deal with the 500 error when flask_babel tries to interpret locale = 'none'
if (navigator.language == 'none') {
    var request = new XMLHttpRequest();
    request.onreadystatechange = function() {
        if (this.readyState == 4) {
            if (this.status == 200) {
                location.reload();
            } else {
                alert('Failed to change language')
            }
        }
    }
    request.open('GET', subdomain + '/lang/de', true);
    request.setRequestHeader("X-Requested-With", "XMLHttpRequest");
    request.send()
}
  
function restrictSearch() {
    var button = document.getElementById('restrictSearchButton');
    var re = new RegExp('&corpus=[^&]*');
    var partRe = new RegExp('&formulaic_parts=[^&]*');
    var corpora = document.getElementsByClassName('corp-restrict-to');
    var parts = document.getElementsByClassName('part-restrict-to');
    var oldUrl = button.getAttribute('href');
    var newCorpora = new Array();
    for (let corp of corpora){
        if (corp.checked) {
            newCorpora.push(corp.getAttribute('value'));
        }
    }
    var newParts = new Array();
    for (let part of parts){
        if (part.checked) {
            newParts.push(part.getAttribute('value'));
        }
    }
    if ( newCorpora.length > 0 ) {
        oldUrl = oldUrl.replace(re, '&corpus=' + newCorpora.join('%2B'));
    }
    if ( newParts.length > 0 ) {
        oldUrl = oldUrl.replace(partRe, '&formulaic_parts=' + newParts.join('%2B'))
    }
    button.setAttribute('href', oldUrl + '&old_search=True');
}

function makeLemmaSearch() {
    var button = document.getElementById('lemmaSearchButton');
    var reQ = new RegExp('&q=[^&]*');
    var reField = new RegExp('&lemma_search=[^&]*');
    var rePage = new RegExp('&page=[^&]*');
    var lemmas = document.getElementsByClassName('lem-to-search');
    var oldUrl = window.location.href;
    var newQ = new Array();
    for (let lemma of lemmas){
        if (lemma.checked || lemma.getAttribute('checked') == 'True') {
            newQ.push(lemma.getAttribute('value'));
        }
    }
    if (Array.isArray(newQ) && newQ.length) {
        oldUrl = oldUrl.replace(reField, '');
        oldUrl = oldUrl.replace(rePage, '');
        button.setAttribute('href', oldUrl.replace(reQ, '&q=' + newQ.join('+')) + '&lemma_search=True');
    } else {
        $('#lemmaSearchButton').popover();
        $('#lemmaSearchButton').popover('toggle');
    }
}

function pdfDownloadWorker() {
    $.get(subdomain + '/search/pdf_progress/' + downloadId, function(data) {
        if (data != '99%') {
            $('#searchDownloadProgress').html(data);
            setTimeout(pdfDownloadWorker, 1000)
        } else {
            $('#searchDownloadProgress').html(data);
        }
    })
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
            var requestUrl;
            if (qSource == "simple") {
                requestUrl = subdomain + '/search/suggest/' + word + buildSimpleUrl("text");
            } else {
                requestUrl = subdomain + '/search/suggest/' + word + buildUrl(qSource);
            }
            var request = $.ajax( requestUrl )
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
function buildSimpleUrl(qSource) {
    var corpus = [];
    var params = {
        corpus:'',
        lemma_search:'autocomplete',
    };
    if (searchLemmas.checked) {
        params.lemma_search = 'autocomplete_lemmas';
    } else {
        params.lemma_search = 'autocomplete';
    }
    $('input[name="corpus"]').each( function(i, subCorp) {
        if (subCorp.checked) {
            corpus.push(subCorp.value);
        }
    });
    params.corpus = corpus.join('+');
    // Build the URL extension
    var brandNewUrl = "?";
    for (f in params) {
        if (f != 'extra_field' && f != 'extra_q') {
            brandNewUrl += f + '=' + params[f] + '&';
        }
    }
    brandNewUrl += 'qSource=' + qSource;
    return brandNewUrl;
}

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

// From https://www.w3schools.com/howto/howto_js_sort_table.asp
function sortSearchResultsTable(n) {
  var table, rows, switching, i, x, y, shouldSwitch, dir, switchcount = 0;
  table = document.getElementById("partsSearchResultTable");
  switching = true;
  // Set the sorting direction to ascending:
  dir = "asc";
  /* Make a loop that will continue until
  no switching has been done: */
  while (switching) {
    // Start by saying: no switching is done:
    switching = false;
    rows = table.rows;
    /* Loop through all table rows (except the
    first, which contains table headers): */
    for (i = 1; i < (rows.length - 1); i++) {
      // Start by saying there should be no switching:
      shouldSwitch = false;
      /* Get the two elements you want to compare,
      one from current row and one from the next: */
      x = rows[i].getElementsByTagName("TD")[n];
      y = rows[i + 1].getElementsByTagName("TD")[n];
      /* Check if the two rows should switch place,
      based on the direction, asc or desc: */
      if (dir == "asc") {
          if (n == 0) {
            if (x.innerHTML.toLowerCase() > y.innerHTML.toLowerCase()) {
            // If so, mark as a switch and break the loop:
            shouldSwitch = true;
            break;
            }
          } else {
              if (x.getAttribute('sortVal').toLowerCase() > y.getAttribute('sortVal').toLowerCase()) {
            // If so, mark as a switch and break the loop:
            shouldSwitch = true;
            break;
            }
        }
      } else if (dir == "desc") {
          if (n == 0) {
            if (x.innerHTML.toLowerCase() < y.innerHTML.toLowerCase()) {
            // If so, mark as a switch and break the loop:
            shouldSwitch = true;
            break;
            }
          } else {
              if (x.getAttribute('sortVal').toLowerCase() < y.getAttribute('sortVal').toLowerCase()) {
            // If so, mark as a switch and break the loop:
            shouldSwitch = true;
            break;
            }
        }
    }
    }
    if (shouldSwitch) {
      /* If a switch has been marked, make the switch
      and mark that a switch has been done: */
      rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
      switching = true;
      // Each time a switch is done, increase this count by 1:
      switchcount ++;
    } else {
      /* If no switching has been done AND the direction is "asc",
      set the direction to "desc" and run the while loop again. */
      if (switchcount == 0 && dir == "asc") {
        dir = "desc";
        switching = true;
      }
    }
  }
}

$(document).ready(function () {
    $('.apparatus-title').append(appHeading);
    $('.commentary-title').append(comHeading);
    $('[id$="a1-hide-button"]').attr('title', appCloseButton)
    $('[id$="a1-show-button"]').attr('title', appOpenButton)
    $('[id$="n1-hide-button"]').attr('title', comCloseButton)
    $('[id$="n1-show-button"]').attr('title', comOpenButton)
    
    $('[data-toggle="tooltip"]').tooltip({trigger: 'manual'})
    
    $('[data-toggle="tooltip"]').on({
        click: function() {
            $( this ).tooltip('hide');
        },
        keydown: function(event) {
            $( this ).tooltip('hide');
        },
        mouseover: function() {
            $( this ).tooltip('show');
        },
        mouseout: function() {
            $( this ).tooltip('hide');
        },
        focusin: function() {
            $( this ).tooltip('show');
        },
        focusout: function() {
            $( this ).tooltip('hide');
        }
    });
    
    //Disable cut, copy, and paste
    $('.no-copy').on('cut copy paste', function (e) {
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

    // from http://jsfiddle.net/zpkKv/2/
    $('#simple-search-q').on('change invalid', function() {
        var textfield = $(this).get(0);
        
        // 'setCustomValidity not only sets the message, but also marks
        // the field as invalid. In order to see whether the field really is
        // invalid, we have to remove the message first
        textfield.setCustomValidity('');
        
        if (!textfield.validity.valid) {
            textfield.setCustomValidity(simpleSearchQMessage);  
        }
    });
    
    $('#searchDownload').on('click', function() {
        var jqxhr = $.ajax( subdomain + "/search/download/" + downloadId )
            .done(function (response, status, xhr) {
                var filename = "";
                var disposition = xhr.getResponseHeader('Content-Disposition');
                if (disposition && disposition.indexOf('attachment') !== -1) {
                    var filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
                    var matches = filenameRegex.exec(disposition);
                    if (matches != null && matches[1]) filename = matches[1].replace(/['"]/g, '');
                }
                var type = xhr.getResponseHeader('Content-Type');
                var blob = new Blob([response], { type: type });
                if (typeof window.navigator.msSaveBlob !== 'undefined') {
                    // IE workaround for "HTML7007: One or more blob URLs were revoked by closing the blob for which they were created. These URLs will no longer resolve as the data backing the URL has been freed."
                    window.navigator.msSaveBlob(blob, filename);
                } else {
                    var URL = window.URL || window.webkitURL;
                    var downloadUrl = URL.createObjectURL(blob);

                    if (filename) {
                        // use HTML5 a[download] attribute to specify filename
                        var a = document.createElement("a");
                        // safari doesn't support this yet
                        if (typeof a.download === 'undefined') {
                            window.location = downloadUrl;
                        } else {
                            a.href = downloadUrl;
                            a.download = filename;
                            document.body.appendChild(a);
                            a.click();
                        }
                    } else {
                        window.location = downloadUrl;
                    }
                }
            })
            .fail(function() {
                alert( downloadError );
            })
            .always(function() {
                $('#searchDownloadProgress').css("visibility", "hidden").html('...');
            });
        // Replace this with a function that repeatedly calls to the backend to find out the status
        // E.g. from https://stackoverflow.com/questions/24251898/flask-app-update-progress-bar-while-function-runs
        $('#searchDownloadProgress').css("visibility", "visible");
        pdfDownloadWorker()
    });
    
    // AJAX request to change locale and then refresh the page
    $('.lang-link').on('click', function(event) {
        event.preventDefault();
        var request = $.ajax( subdomain + '/lang/' + $( this ).attr('value') )
            .done( function () {
                location.reload();
            })
            .fail(function() {
                alert('Failed to change language');
            });
    })
    
    $('[data-toggle="popover"]').popover()
    
    
    $('#simple-search-q').keyup(function(e) {
        sendAutocompleteRequest($( this ), $('#simple-search-datalist'), "simple");
    });
    
    $('#manuscript-table dt').hover(function() {
        $( this ).css("background-color", "lightgrey");
        $( this ).next().css("background-color", "lightgrey");
    },
    function() {
        $( this ).css("background-color", "inherit");
        $( this ).next().css("background-color", "inherit");
    });
    
    $('#manuscript-table dd').hover(function() {
        $( this ).css("background-color", "lightgrey");
        $( this ).prev().css("background-color", "lightgrey");
    },
    function() {
        $( this ).css("background-color", "inherit");
        $( this ).prev().css("background-color", "inherit");
    });
    
    $('#partsSearchResultTable #results-text-column').click(function() {sortSearchResultsTable(0)});
    $('#partsSearchResultTable #results-date-column').click(function() {sortSearchResultsTable(1)});
    $('#partsSearchResultTable #results-title-column').click(function() {sortSearchResultsTable(2)});
    
    $('#partsSearchResultTable #results-text-column').trigger('click');
    
    $('#restrictSearchButton').click(function() {
        restrictSearch();
    })
    
    $('.corpora-search-results-dropdown label').on('click', function () {
        $( this ).siblings('input').click();
        return false;
    });
    
    $('.part-menu-dropdown').on('click', 'label', function () {
        $( this ).siblings('input').click();
        return false;
    });
})
