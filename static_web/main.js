Array.prototype.remove = function () {
    var what, a = arguments, L = a.length, ax;
    while (L && this.length) {
        what = a[--L];
        while ((ax = this.indexOf(what)) !== -1) {
            this.splice(ax, 1);
        }
    }
    return this;
};

var trackers = {
    'yeet': {},
    'yoink': {}
};

function set_tracker_element(method, id, percentage, title) {
    if ($('#tracker-list').children('#'+id).length == 0) {
        if (method == 'yeet') {
            var m = 'file_upload';
        } else {
            var m = 'file_download';
        }
        $('#tracker-list').append(
            $('<div class="tracker-item shadow-sm"></div>')
                .attr('id', id)
                .append($('<span class="material-icons"></span>').text(m))
                .append($('<span class="title"></span>').text(title))
                .append(
                    $('<span class="progress-wrapper"></span>')
                        .append(
                            $('<span class="progress-bar"></span>')
                        )
                )
        );
    }
    $('#tracker-list').children('#'+id).children('.progress-wrapper').children('.progress-bar')
        .css('width', Math.round(percentage * 100)+'%');
    if (percentage > 0.9999) {
        $('#tracker-list').children('#'+id).remove();
    }
}

function update_tracker(type, id, percentage, lp, rp) {
    if (!Object.keys(trackers[type]).includes(id)) {
        trackers[type][id] = {
            'local': lp,
            'remote': rp,
            'progress': 0
        };
    }
    if (type == 'yeet') {
        var title = lp;
    } else {
        var title = rp;
    }
    trackers[type][id]['progress'] = percentage;
    set_tracker_element(type, id, percentage, title);
    if (percentage > 0.9999) {
        delete trackers[type][id];
        eel.profiles()(js_update);
    }
}
window.eel.expose(update_tracker, 'update_tracker');

async function js_update(profiles) {
    window.onresize = function () {
        if (window.outerWidth < 1200 || window.outerHeight < 800) {
            window.resizeTo(1200, 800);
        }
    }
    console.log(profiles);
    var dummyNetList = $('<div id="network-list" class="scroll1"></div>');
    var data = JSON.parse(localStorage.getItem('yeetyoink_data'));
    data.connections = await eel.list_connections()();
    localStorage.setItem('yeetyoink_data', JSON.stringify(data));
    for (profile of Object.values(profiles)) {
        var netItem = $('<div class="network-profile-item shadow-sm"></div>');
        netItem.attr('data-id', profile.id);
        netItem.toggleClass('connected', data.connections.includes(profile.id));
        if (data.connections.includes(profile.id)) {
            netItem.append('<span class="material-icons main-icon noselect">public</span>');
        } else {
            netItem.append('<span class="material-icons main-icon noselect">public_off</span>');
        }
        netItem.append($('<span class="item-display-name noselect"></span>').text(profile.display_name));
        netItem.append($('<span class="item-network-name"></span>').text(profile.network_name));
        netItem.append(
            $('<button class="item-remove shadow-sm2 noselect"></button>')
                .append('<span class="material-icons">delete</span>')
                .on('click', function () {
                    eel.remove_profile($(this).parents('.network-profile-item').attr('data-id'));
                })
        );
        netItem.children('.main-icon').on('click', function () {
            console.log('click');
            var data = JSON.parse(localStorage.getItem('yeetyoink_data'));
            if ($(this).parents('.network-profile-item').hasClass('connected')) {
                eel.disconnect($(this).parents('.network-profile-item').attr('data-id'));
                data.connections.remove($(this).parents('.network-profile-item').attr('data-id'));
                $(this).text('public_off');
            } else {
                eel.connect($(this).parents('.network-profile-item').attr('data-id'));
                data.connections.push($(this).parents('.network-profile-item').attr('data-id'));
                $(this).text('public');
            }
            localStorage.setItem('yeetyoink_data', JSON.stringify(data));
        });

        dummyNetList.append(netItem);
    }
    dummyNetList.replaceAll('#network-list');

    eel.list_peers()(function (result) {
        var dummyOptions = $('<select id="remote-node-select"></select>');
        for (peer of result) {
            dummyOptions.append(
                $('<option></option>')
                    .attr('value', peer[1] + '|' + peer[0])
                    .text(peer[0].split('-srv')[0])
            );
        }
        dummyOptions.replaceAll('#remote-node-select');
        var data = JSON.parse(localStorage.getItem('yeetyoink_data'));
        console.log(data);
        if (data.current_node) {
            $('#remote-node-select').val(data.current_node);
        } else {
            data.current_node = $('#remote-node-select').val();
        }
        localStorage.setItem('yeetyoink_data', JSON.stringify(data));
        $('#remote-file-browser .path-input').val(JSON.parse(localStorage.getItem('yeetyoink_data')).remote_path);
        if (data.current_node) {
            if ($('#remote-node-select').val() == null) {
                localStorage.removeItem('yeetyoink_data');
                window.location.reload();
            }
            eel.listdir_remote(
                $('#remote-node-select').val().split('|')[0],
                $('#remote-node-select').val().split('|')[1],
                JSON.parse(localStorage.getItem('yeetyoink_data')).remote_path
            )(function (dirs) {
                console.log(dirs);
                var dummyRemoteFileBrowser = $("<div class='browser-files'></div>");
                dummyRemoteFileBrowser.append(
                    $('<div class="file-item folder parent-link noselect"></div>')
                        .append(
                            $('<span class="material-icons">folder_open</span>')
                        )
                        .append(
                            $('<span class="item-name">..</span>')
                        )
                        .on('click', function () {
                            $('.file-item.selected').removeClass('selected');
                            $(this).toggleClass('selected');
                        })
                        .on('dblclick', function () {
                            var data = JSON.parse(localStorage.getItem('yeetyoink_data'));
                            var pathparts = data.remote_path.split('/');
                            if (pathparts[pathparts.length - 1] == '') {
                                pathparts.pop();
                            }
                            if (pathparts.length > 1) {
                                console.log(pathparts);
                                pathparts.pop();
                                data.remote_path = pathparts.join('/');
                                localStorage.setItem('yeetyoink_data', JSON.stringify(data));
                                eel.profiles()(js_update);
                            }
                        })
                );
                for (dir of dirs) {
                    if (dir[1]) {
                        dummyRemoteFileBrowser.append(
                            $('<div class="file-item file parent-link noselect"></div>')
                                .append(
                                    $('<span class="material-icons">description</span>')
                                )
                                .append(
                                    $('<span class="item-name"></span>').text(dir[0])
                                )
                                .on('click', function () {
                                    $('.file-item.selected').removeClass('selected');
                                    $(this).toggleClass('selected');
                                })
                                .append(
                                    $('<button class="yoink-btn">YOINK</button>')
                                        .on('click', function () {
                                            if (JSON.parse(localStorage.getItem('yeetyoink_data')).current_node == null) {
                                                return;
                                            }
                                            var local = JSON.parse(localStorage.getItem('yeetyoink_data')).local_path;
                                            var remote = JSON.parse(localStorage.getItem('yeetyoink_data')).remote_path;
                                            if (remote[remote.length - 1] == '/') {
                                                remote += $(this).parents('.file-item').children('.item-name').text();
                                            } else {
                                                remote += '/' + $(this).parents('.file-item').children('.item-name').text();
                                            }
                                            console.log(local, remote);
                                            eel.yoink(
                                                $('#remote-node-select').val().split('|')[0],
                                                $('#remote-node-select').val().split('|')[1],
                                                local,
                                                remote
                                            );
                                        })
                                )
                                .append(
                                    $('<button class="bonk-btn">BONK</button>')
                                        .on('click', function () {
                                            if (JSON.parse(localStorage.getItem('yeetyoink_data')).current_node == null) {
                                                return;
                                            }
                                            var remote = JSON.parse(localStorage.getItem('yeetyoink_data')).remote_path;
                                            if (remote[remote.length - 1] == '/') {
                                                remote += $(this).parents('.file-item').children('.item-name').text();
                                            } else {
                                                remote += '/' + $(this).parents('.file-item').children('.item-name').text();
                                            }
                                            eel.bonk(
                                                $('#remote-node-select').val().split('|')[0],
                                                $('#remote-node-select').val().split('|')[1],
                                                remote
                                            );
                                        })
                                )
                        );
                    } else {
                        dummyRemoteFileBrowser.append(
                            $('<div class="file-item folder parent-link noselect"></div>')
                                .append(
                                    $('<span class="material-icons">folder</span>')
                                )
                                .append(
                                    $('<span class="item-name"></span>').text(dir[0])
                                )
                                .on('click', function () {
                                    $('.file-item.selected').removeClass('selected');
                                    $(this).toggleClass('selected');
                                })
                                .on('dblclick', function () {
                                    var data = JSON.parse(localStorage.getItem('yeetyoink_data'));
                                    if (data.remote_path[data.remote_path.length - 1] == '/') {
                                        data.remote_path = data.remote_path + $(this).children('.item-name').text();
                                    } else {
                                        data.remote_path = data.remote_path + '/' + $(this).children('.item-name').text();
                                    }
                                    localStorage.setItem('yeetyoink_data', JSON.stringify(data));
                                    eel.profiles()(js_update);
                                })
                                .append(
                                    $('<button class="bonk-btn">BONK</button>')
                                        .on('click', function () {
                                            if (JSON.parse(localStorage.getItem('yeetyoink_data')).current_node == null) {
                                                return;
                                            }
                                            var remote = JSON.parse(localStorage.getItem('yeetyoink_data')).remote_path;
                                            if (remote[remote.length - 1] == '/') {
                                                remote += $(this).parents('.file-item').children('.item-name').text();
                                            } else {
                                                remote += '/' + $(this).parents('.file-item').children('.item-name').text();
                                            }
                                            eel.bonk(
                                                $('#remote-node-select').val().split('|')[0],
                                                $('#remote-node-select').val().split('|')[1],
                                                remote
                                            );
                                        })
                                )
                        );
                    }
                }
                dummyRemoteFileBrowser.replaceAll('#remote-file-browser .browser-files');
            });
        } else {
            $("<div class='browser-files'></div>").replaceAll('#remote-file-browser .browser-files');
        }
    });

    $('#local-file-browser .path-input').val(JSON.parse(localStorage.getItem('yeetyoink_data')).local_path);
    eel.listdir_local(JSON.parse(localStorage.getItem('yeetyoink_data')).local_path)(function (dirs) {
        console.log(dirs);
        var dummyLocalFileBrowser = $("<div class='browser-files'></div>");
        dummyLocalFileBrowser.append(
            $('<div class="file-item folder parent-link noselect"></div>')
                .append(
                    $('<span class="material-icons">folder_open</span>')
                )
                .append(
                    $('<span class="item-name">..</span>')
                )
                .on('click', function () {
                    $('.file-item.selected').removeClass('selected');
                    $(this).toggleClass('selected');
                })
                .on('dblclick', function () {
                    var data = JSON.parse(localStorage.getItem('yeetyoink_data'));
                    var pathparts = data.local_path.replace(/:/g, '``colon``').split('/');
                    if (pathparts[pathparts.length - 1] == '') {
                        pathparts.pop();
                    }
                    if (pathparts.length > 1) {
                        console.log(pathparts);
                        pathparts.pop();
                        data.local_path = pathparts.join('/').replace(/``colon``/g, ':');
                        if (data.local_path[data.local_path.length - 1] != '/') {
                            data.local_path += '/';
                        }
                        localStorage.setItem('yeetyoink_data', JSON.stringify(data));
                        eel.profiles()(js_update);
                    }
                })
        );
        for (dir of dirs) {
            if (dir[1]) {
                dummyLocalFileBrowser.append(
                    $('<div class="file-item file parent-link noselect"></div>')
                        .append(
                            $('<span class="material-icons">description</span>')
                        )
                        .append(
                            $('<span class="item-name"></span>').text(dir[0])
                        )
                        .on('click', function () {
                            $('.file-item.selected').removeClass('selected');
                            $(this).toggleClass('selected');
                        })
                        .append(
                            $('<button class="yeet-btn">YEET</button>')
                                .on('click', function () {
                                    if (JSON.parse(localStorage.getItem('yeetyoink_data')).current_node == null) {
                                        return;
                                    }
                                    var local = JSON.parse(localStorage.getItem('yeetyoink_data')).local_path;
                                    var remote = JSON.parse(localStorage.getItem('yeetyoink_data')).remote_path;
                                    if (local[local.length - 1] == '/') {
                                        local += $(this).parents('.file-item').children('.item-name').text();
                                    } else {
                                        local += '/' + $(this).parents('.file-item').children('.item-name').text();
                                    }
                                    console.log(local, remote);
                                    eel.yeet(
                                        $('#remote-node-select').val().split('|')[0],
                                        $('#remote-node-select').val().split('|')[1],
                                        local,
                                        remote
                                    );
                                })
                        )
                );
            } else {
                dummyLocalFileBrowser.append(
                    $('<div class="file-item folder parent-link noselect"></div>')
                        .append(
                            $('<span class="material-icons">folder</span>')
                        )
                        .append(
                            $('<span class="item-name"></span>').text(dir[0])
                        )
                        .on('click', function () {
                            $('.file-item.selected').removeClass('selected');
                            $(this).toggleClass('selected');
                        })
                        .on('dblclick', function () {
                            var data = JSON.parse(localStorage.getItem('yeetyoink_data'));
                            if (data.local_path[data.local_path.length - 1] == '/') {
                                data.local_path = data.local_path + $(this).children('.item-name').text();
                            } else {
                                data.local_path = data.local_path + '/' + $(this).children('.item-name').text();
                            }
                            localStorage.setItem('yeetyoink_data', JSON.stringify(data));
                            eel.profiles()(js_update);
                        })
                );
            }
        }
        dummyLocalFileBrowser.replaceAll('#local-file-browser .browser-files');
    });
}
window.eel.expose(js_update, 'js_update');

$(document).ready(async function () {
    $('#new-connection').on('click', function () {
        $('#new-connection-form input').val('');
        $('#new-connection-form').toggleClass('selected');
    });
    $('#finish-new-connection').on('click', function () {
        if (
            $('#display-name-input').val().length > 0 &&
            $('#network-name-input').val().length > 0 &&
            !$('#network-name-input').val().includes(':') &&
            !$('#network-name-input').val().includes('|') &&
            !$('#network-name-input').val().includes('.') &&
            $('#network-key-input').val().length == 44 &&
            $('#network-port-input').val().length > 3 &&
            !isNaN(Number($('#network-port-input').val()))
        ) {
            if ($('#remotes-input').val().length == 0) {
                var remotes = [];
            } else {
                var remotes = $('#remotes-input').val().replace(/ /g, '').split(',');
            }
            if (remotes.every(function (v, i, a) {
                return /[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}:[0-9]{1,5}/g.test(v);
            })) {
                if (remotes == []) {
                    remotes = null;
                }
                eel.new_profile(
                    $('#display-name-input').val(),
                    $('#network-name-input').val(),
                    $('#network-key-input').val(),
                    Number($('#network-port-input').val()),
                    remotes
                );
                $('#new-connection-form').removeClass('selected');
                return;
            }
        }
        $('#finish-new-connection').addClass('invalid');
        setTimeout(function () {
            $('#finish-new-connection').removeClass('invalid');
        }, 1000);
    });
    $('#local-file-browser .path-input').on('change', function () {
        var data = JSON.parse(localStorage.getItem('yeetyoink_data'));
        data.local_path = $(this).val();
        localStorage.setItem('yeetyoink_data', JSON.stringify(data));
        eel.profiles()(js_update);
    });
    $('#remote-file-browser .path-input').on('change', function () {
        var data = JSON.parse(localStorage.getItem('yeetyoink_data'));
        data.remote_path = $(this).val();
        localStorage.setItem('yeetyoink_data', JSON.stringify(data));
        eel.profiles()(js_update);
    });
    $('#boop-remote').on('click', function () {
        if (JSON.parse(localStorage.getItem('yeetyoink_data')).current_node == null) {
            return;
        }
        var folder_name = prompt('Enter Folder Name');
        var remote = JSON.parse(localStorage.getItem('yeetyoink_data')).remote_path;
        if (remote[remote.length - 1] == '/') {
            remote += folder_name;
        } else {
            remote += '/' + folder_name;
        }
        eel.boop(
            $('#remote-node-select').val().split('|')[0],
            $('#remote-node-select').val().split('|')[1],
            remote
        );
    });
    $('#remote-node-select').on('change', function () {
        var data = JSON.parse(localStorage.getItem('yeetyoink_data'));
        data.current_node = $('#remote-node-select').val();
        localStorage.setItem('yeetyoink_data', JSON.stringify(data));
        eel.profiles()(js_update);
    });

    var cwd = await eel.get_cwd()();
    if (!localStorage.getItem('yeetyoink_data')) {
        localStorage.setItem('yeetyoink_data', JSON.stringify({
            'connections': [],
            'current_node': null,
            'local_path': cwd,
            'remote_path': ''
        }));
    }
    eel.profiles()(js_update);
});