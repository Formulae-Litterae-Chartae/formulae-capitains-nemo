$(document).ready(function () {
    $('.reading-sidebar').each(function() {
        $( this ).css('max-width', '33%');
        $( this ).css('min-width', '0');
        $( this ).removeClass('d-none d-lg-block')
    });
    
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
        });
    });
});

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

// Allow texts when in rows reading format to be expanded and contracted by the user
$( function() {
    $('.multi-reading-row').resizable({
        handles: "s",
    });
    } );
