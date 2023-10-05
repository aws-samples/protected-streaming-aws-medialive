import videojs from 'video.js';

videojs.log.level('debug');

function videoplayerElem() {
    
    var video = document.createElement('video')
    var source = document.createElement('source')
    
    video.setAttribute('id','protected-player');
    video.setAttribute('class','video-js');
    source.setAttribute('type', 'application/x-mpegURL');
    source.setAttribute('src', '/prod/pipe-1/media.m3u8')

    console.log(video);

    video.appendChild(source);

    return video;
}

document.body.appendChild(videoplayerElem());


var options = {liveui: true};
var player = videojs('protected-player', options, 
    function onPlayerReady(){
        videojs.log('Video player loaded');
        this.width(960);
        this.height(540);
        this.controls(true);
        videojs.log('Duration after loading: '+this.duration())
    }
);

player.on('play', 
    function onPlayerPlay(){
        videojs.log('Play event triggered')
        videojs.log('Duration when playing: '+this.duration())
    }
);

