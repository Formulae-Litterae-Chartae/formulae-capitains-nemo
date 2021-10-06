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
    document.getElementById('elexiconSearchCorpus').checked = false;
}

function uncheckAllCorpora() {
    var subelements = document.getElementsByClassName('under-all');
    var l = subelements.length;
    var i;
    for(i = 0; i < l; i++) {
        subelements[i].checked = false;
    }
    document.getElementById('all').checked = false;
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
    $('.word-search-box').keyup(function(e) {
        sendAutocompleteRequest($( this ));
    });
     
    var datePlusMinusInput = document.getElementById('date_plus_minus');
    var slopInput = document.getElementsByClassName('slop_input');

    datePlusMinusInput.addEventListener('input', function () {
        datePlusMinusInput.setCustomValidity("");
        datePlusMinusInput.checkValidity();
    })

    datePlusMinusInput.addEventListener('invalid', function () {
        datePlusMinusInput.setCustomValidity(datePlusMinusInvalidMessage);
    })

    for (let item of slopInput) {
        item.addEventListener('input', function () {
            item.setCustomValidity("");
            item.checkValidity();
        })
        item.addEventListener('invalid', function () {
            item.setCustomValidity(slopInvalidMessage);
            
        })
    }
    
    $('.corpus-ul .collapse input').each(function(i, el) {
        if ($( this ).attr('type') == "checkbox") {
            if ($( this ).prop('checked') && $( this ).attr('id') != "firstLetter") {
                var collapseParent = $( this ).parents('#formulaeCorporaCollapse,#chartaeCorporaCollapse');
                if (collapseParent.length && collapseParent.find('input:checked').length == collapseParent.find('input').length) {
                    collapseParent.prev('li').find('input[type="checkbox"]').prop( "checked", true);
                } else {
                    $( this ).parents('.collapse').show();
                }
            }
        } else {
            if ($( this ).val() && $( this ).val() != "0") {
                $( this ).parents('.collapse').show();
            }
        }
    });
    
    $('.corpus-ul .collapse option:checked').each(function(i, el) {
        if ($( this ).val() != "0") {
            $( this ).parents('.collapse').show();
        }
    });
    
    $('.search-mask').click(function() {
        var button = $( this ).find('button');
        if ( button.text() == button.attr('data-new') ) {
            button.text(button.attr('data-original'));
        } else {
            button.text(button.attr('data-new'));
        };
        var new_target = $( $( this ).attr('next') );
        var new_button = new_target.find('button');
        if ( new_target.hasClass('d-none') ) {
            new_target.removeClass('d-none');
        } else {
            new_target.addClass('d-none');
            $( new_button.attr('data-target') ).collapse('hide');
            new_button.text(new_button.attr('data-original'));
            if ( new_target.attr('next') ) {
                $( new_target.attr('next') ).addClass('d-none');
                var newer_button = $( $( new_target.attr('next') ).find('button') );
                $( newer_button.attr('data-target') ).collapse('hide');
                newer_button.text(newer_button.attr('data-original'));
            };
        };
    });
})
