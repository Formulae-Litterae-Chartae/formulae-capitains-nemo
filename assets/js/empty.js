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
    var oldUrl = window.location.href;
    var newQ = new Array();
    for (let lemma of lemmas){
        if (lemma.checked || lemma.getAttribute('checked') == 'True') {
            newQ.push(lemma.getAttribute('value'));
        }
    };
    if (Array.isArray(newQ) && newQ.length) {
        oldUrl = oldUrl.replace(reField, '');
        oldUrl = oldUrl.replace(rePage, '');
        button.setAttribute('href', oldUrl.replace(reQ, '&q=' + newQ.join('+')) + '&lemma_search=True');
    } else {
        $('#lemmaSearchButton').popover();
        $('#lemmaSearchButton').popover('toggle');
    }
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
    };

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
        var jqxhr = $.ajax( "/search/download/" + downloadId )
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
    })
    
});

function pdfDownloadWorker() {
    $.get('/search/pdf_progress/' + downloadId, function(data) {
        if (data != '99%') {
            $('#searchDownloadProgress').html(data);
            setTimeout(pdfDownloadWorker, 1000)
        } else {
            $('#searchDownloadProgress').html(data);
        }
    })
}
