if (window.innerWidth < 992) {
    var splitSizes = [25, 50, 25];
} else {
    var splitSizes = [16, 68, 16];
};

$(document).ready(function () {
    if ( screen.width > 767 ) {
        // use Split to show notes
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
        
        $('.gutter.gutter-horizontal').keydown( function(event) {
            if ( $( this ).hasClass( "order-2" ) ) {
                var indOne = 0;
                var indTwo = 1;
            } else if ( $( this ).hasClass( "order-3" ) ) {
                var indOne = 1;
                var indTwo = 2;
            } else {
                return;
            };
            var widths = splitInstance.getSizes();
            var key = event.charCode || event.keyCode;
            if (key == 37) {
                event.preventDefault();
                if (widths[indOne] >= 0.5) {
                    widths[indOne] = widths[indOne] - 1;
                    widths[indTwo] = widths[indTwo] + 1;
                };
            } else if (key == 39) {
                event.preventDefault();
                if (widths[indTwo] >= 0.5) {
                    widths[indOne] = widths[indOne] + 1;
                    widths[indTwo] = widths[indTwo] - 1;
                };
            };
            splitInstance.setSizes(widths);
        });
    }
    
    // Allow texts when in rows reading format to be expanded and contracted by the user
    $('.multi-reading-row,.notecard-row').resizable({
        handles: "s",
    });
    
    $('.ui-resizable-handle.ui-resizable-s').attr('tabindex', '0');
    $('.ui-resizable-handle.ui-resizable-s').addClass('text-center');
    $('.ui-resizable-handle.ui-resizable-s').html('<img src="' + handleBackgroundImage + '" alt="Horizontal Handle">');
    
    $('.ui-resizable-handle.ui-resizable-s').keydown( function(event) {
        var parent = $( this ).closest('.multi-reading-row');
        var curr_ht = parent.height();
        var key = event.charCode || event.keyCode;
        if (key == 38) {
            event.preventDefault();
            parent.height( curr_ht - 10 )
        } else if (key == 40) {
            event.preventDefault();
            parent.height( curr_ht + 10 )
        };
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
        if (formTypes.length > 0) {
            $(".part-menu-icon").css('display', 'block');
        }
        for ( t of formTypes ) {
            var menuItem = $("<span></span>").attr("class", "dropdown-item").attr("value", t);
            var inputItem = $("<input></input>").attr({"class" : "show-parts", "type" : "checkbox", "value" : t, 'id': t});
            menuItem.append(inputItem);
            menuItem.append($("<label>" + t + "</label>").attr('for', t));
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
    
    $('.part-menu-icon').draggable({
        stack: '.part-menu-icon',
        handle: '.part-menu-handle'
    });
})

var splitInstance = Split(['#sidebar_l', '#reading-container', '#sidebar_r'], {
    sizes: splitSizes,
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
    gutter: (index, direction, pairElement) => {
        const gutter = document.createElement('div')
        gutter.setAttribute("tabindex", "0");
        var order = 2;
        if (pairElement.id == 'sidebar_r') {
            order = 3
        } 
        gutter.className = `gutter gutter-${direction} order-${order}`
        return gutter
    },
    gutterStyle: (dimension, gutterSize) => ({
        'flex-basis':  `${gutterSize}px`,
    }),
})
