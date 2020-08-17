$(document).ready(function () {
    $('.reading-sidebar').each(function() {
        $( this ).css('max-width', '33%');
        $( this ).css('min-width', '0');
        $( this ).removeClass('d-none d-lg-block')
    })
    
    $('#sidebar_r').css('padding-left', '0px');

    $('#sidebar_l').css('padding-right', '0px');

    $('#reading-container').css({
        "padding-left": '0px',
        "padding-right": '0px'
    });
    
    $('.gutter.gutter-horizontal').each(function() {
        $( this ).css({
            'visibility': 'visible',
            'background-image': gutterBackgroundImage,
            'z-index': 1000
        })
    })
    
    // Allow texts when in rows reading format to be expanded and contracted by the user
    $('.multi-reading-row').resizable({
        handles: "s",
    });
    
    $('.multi-reading-row').each(function() {
        $( this ).css("height", "40vh");
    })

    // Allow user to automatically maximize the window for a text
    $('.maximize-column-link').click(function() {
        $( this ).closest('article').css('height', 'auto');
    })

    // Allow user to automatically minimize the window for a text
    $('.minimize-column-link').click(function() {
        $( this ).closest('article').css('height', '40vh');
    })
    
    // Allow user to maximize all reading rows at once
    $('#max-rows-image').click(function() {
        $('.multi-reading-row').each(function() {
            $( this ).css('height', 'auto');
        })
    })
    
    // Allow user to minimize all reading rows at once
    $('#min-rows-image').click(function() {
        $('.multi-reading-row').each(function() {
            $( this ).css('height', '40vh');
        })
    })
    
    // Highlight formulaic parts of the texts
    $('.text-section,.text-row').each( function() {
        var formTypes = [];
        $( this ).find('span[function]').each( function() {
            var formType = $( this ).attr('function');
            if ( formType && !(formTypes.includes(formType)) ) {
                formTypes.push(formType);
            }
        });
        for ( t of formTypes ) {
            var menuItem = $("<span></span>").attr("class", "dropdown-item").attr("value", t);
            menuItem.append($("<input> " + t + "</input>").attr({"class" : "show-parts", "type" : "checkbox", "value" : t}));
            $( this ).prev('.control-row').find('.part-menu-dropdown').first().append(menuItem)
        }
    } );
    
    $('.part-menu-dropdown .show-all-parts').prop('checked', false); 
    
    $('.part-menu-dropdown .show-parts').click( function() {
        var selectedPart = $( this ).attr('value');
        var childCheck = $( this ).children();
        $( this ).parents('.control-row').first().next('.text-section,.text-row').find('span[function="' + selectedPart + '"]').each( function() {
            $( this ).toggleClass(selectedPart + '-bg');
        })
    });
    
    $('.part-menu-dropdown .show-all-parts').click( function() {
        origElement = $( this );
        if (origElement.prop('checked')) {
            origElement.next('label').text(hideAllPartsMessage);
        } else {
            origElement.next('label').text(showAllPartsMessage);
        }
        origElement.parents('.part-menu-dropdown').find('input.show-parts').each( function() {
            if ($( this ).prop('checked') != origElement.prop('checked')) {
                $( this ).trigger('click');
            }
        });
    });
})

Split(['#sidebar_l', '#reading-container', '#sidebar_r'], {
    sizes: [16, 68, 16],
    minSize: [0, 100, 0],
    elementStyle: function(dimension, size, gutterSize) {
        if (size > 0.5) {
            return {
                'flex-basis': `calc(${size}% - ${gutterSize}px)`,
                'display': 'block'
            }
        } else {
            return {
                'display': 'none'
            }
        }
    },
    gutterStyle: (dimension, gutterSize) => ({
        'flex-basis':  `${gutterSize}px`,
    }),
})
