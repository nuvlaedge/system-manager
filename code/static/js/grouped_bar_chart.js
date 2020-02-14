Chart.defaults.global.defaultFontColor = "rgba(230, 230, 230, 0.6)";

var chartOptions = {
  responsive: true,
  legend: {
    position: "top"
  },
  title: {
    display: false
  },
  scales: {
    yAxes: [{
      gridLines: {
        color: "rgba(220, 220, 220, 0.1)"
      },
      scaleLabel: {
        labelString: "bytes",
        display: true,
        fontColor: "rgba(220, 220, 220, 0.8)"
      },
      ticks: {
        beginAtZero: true
      },
      type: 'logarithmic'
    }],
    xAxes: [{
      gridLines: {
        color: "rgba(220, 220, 220, 0.1)"
      },
      scaleLabel: {
        labelString: "interface",
        display: true,
        fontColor: "rgba(220, 220, 220, 0.8)"
      },
    }]
  }
}
