    var collapsed_r = false;

    $(document).ready(function () {
        $('#sidebarCollapse_r').on('click', function () {
            $('#sidebar_r').toggleClass('active');
            console.lod("HAI");
            var el_r = document.getElementById('sidebarCollapse_r');

            if (collapsed_r){
                collapsed_r = false;
                console.lod(collapsed_r);
                el_r.firstChild.data = ">";
            }else{
                collapsed_r = true;
                console.lod(collapsed_r);
                el_r.firstChild.data = "<";
            }
        });


        $('#sidebarCollapse_l').on('click', function () {
            $('#sidebar_l').toggleClass('active');
            var el_l = document.getElementById('sidebarCollapse_l');
            if ($('#sidebar_l').css("marginLeft")=='0px'){
                el_l.firstChild.data = "<";
            }else{
                el_l.firstChild.data = ">";
            }
        });

    });


