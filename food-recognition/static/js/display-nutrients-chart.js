var csv_file = document.querySelector("#csv_file");
var csv_file2 = document.querySelector("#csv_file2");
var canvas1 = document.querySelector("#container1");
var canvas2 = document.querySelector("#container2");

var filename = csv_file.textContent;
var filename2 = csv_file2.textContent;

var TITLE = 'Nutrients Statistics Chart';
var HORIZONTAL = false;
var STACKED = true;
var LABELS = 'names';

var SERIES = [
    { column: 'calories', name: 'calories', color: 'red' },
    { column: 'protein', name: 'protein', color: 'green' },
    { column: 'fat', name: 'fat', color: 'blue' },
    { column: 'carbs', name: 'carbs', color: 'yellow' },
    { column: 'fiber', name: 'fiber', color: 'purple' }
];

var X_AXIS = 'Elements Info';
var Y_AXIS = 'Amount';
var SHOW_GRID = true;
var SHOW_LEGEND = true;

function getChart(val) {
    if (val.value === "1") {
        $('#display-chart').empty();
        canvas1.style.display = "block";
        canvas2.style.display = 'none';

        // 读取csv，创建图表
        $.get(filename, {'_': $.now()}, function(csvString) {
            let rows = Papa.parse(csvString, {header: true, skipEmptyLines: true}).data;

            let datasets = SERIES.map(function(el) {
                return {
                    label: el.name,
                    labelDirty: el.column,
                    backgroundColor: el.color,
                    data: []
                }
            });

            rows.map(function(row) {
                datasets.map(function(d) {
                    d.data.push(row[d.labelDirty])
                })
            });

            let barChartData = {
                labels: rows.map(function(el) { return el[LABELS] }),
                datasets: datasets
            };

            let ctx = document.getElementById('container1').getContext('2d');
            new Chart(ctx, {
                type: HORIZONTAL ? 'horizontalBar' : 'bar',
                data: barChartData,
                options: {
                    title: { display: true, text: TITLE, fontSize: 20 },
                    legend: { display: SHOW_LEGEND },
                    scales: {
                        xAxes: [{
                            stacked: STACKED,
                            scaleLabel: { display: X_AXIS !== '', labelString: X_AXIS },
                            gridLines: { display: SHOW_GRID },
                            ticks: {
                                beginAtZero: true,
                                callback: function(value) { return value.toLocaleString(); }
                            }
                        }],
                        yAxes: [{
                            stacked: STACKED,
                            beginAtZero: true,
                            scaleLabel: { display: Y_AXIS !== '', labelString: Y_AXIS },
                            gridLines: { display: SHOW_GRID },
                            ticks: {
                                beginAtZero: true,
                                callback: function(value) { return value.toLocaleString(); }
                            }
                        }]
                    },
                    tooltips: {
                        displayColors: false,
                        callbacks: {
                            label: function(tooltipItem, all) {
                                return all.datasets[tooltipItem.datasetIndex].label + ': ' + tooltipItem.yLabel.toLocaleString();
                            }
                        }
                    }
                }
            });

            // =========== AI 智能营养建议自动请求与展示 ==========
            if (rows.length > 0) {
                let nutrients = {
                    calories: parseFloat(rows[0]['calories']),
                    protein: parseFloat(rows[0]['protein']),
                    fat: parseFloat(rows[0]['fat']),
                    carbs: parseFloat(rows[0]['carbs']),
                    fiber: parseFloat(rows[0]['fiber'])
                };
                let requestData = {
                    food: rows[0]['names'] || "Unknow Food",
                    nutrients: nutrients,
                    user_info: {
                        age: 25,
                        sex: "male",
                        goal: "keep fit"
                    }
                };

                // 显示加载提示
                document.getElementById('ai-analysis').innerText = "Getting AI suggestions......";

                fetch('/api/nutrition/llm_analysis', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(requestData)
                })
                .then(response => response.json())
                .then(data => {
                    document.getElementById('ai-analysis').innerText = data.llm_analysis || "NO SUGGESTION!";
                })
                .catch(err => {
                    document.getElementById('ai-analysis').innerText = "ERROR!：" + err;
                });
            }
            // =========== AI 智能营养建议自动请求与展示结束 ==========
        });
    }
    else {
        $('#display-chart').empty();
        canvas2.style.display = "block";
        canvas1.style.display = 'none';

        $.get(filename2, {'_': $.now()}, function(csvString) {
            let rows = Papa.parse(csvString, {header: true, skipEmptyLines: true}).data;
            let names = Object.keys(rows[0]).slice(1);

            let SERIES1 = [];
            let info = ['calories', 'protein', 'fat', 'carbs', 'fiber'];

            for(let i=0; i<names.length; i++){
                let randomColor = Math.floor(Math.random()*16777215).toString(16);
                let colour = "#" + randomColor;
                SERIES1.push({ column: names[i], name: names[i], color: colour });
            }

            let datasets = SERIES1.map(function(el) {
                return {
                    label: el.name,
                    labelDirty: el.column,
                    backgroundColor: el.color,
                    data: []
                }
            });

            rows.map(function(row) {
                datasets.map(function(d) {
                    d.data.push(row[d.labelDirty])
                })
            });

            let barChartData = {
                labels: info,
                datasets: datasets
            };

            var ctx = document.getElementById('container2').getContext('2d');
            new Chart(ctx, {
                type: HORIZONTAL ? 'horizontalBar' : 'bar',
                data: barChartData,
                options: {
                    title: { display: true, text: TITLE, fontSize: 20 },
                    legend: { display: SHOW_LEGEND },
                    scales: {
                        xAxes: [{
                            stacked: STACKED,
                            scaleLabel: { display: X_AXIS !== '', labelString: X_AXIS },
                            gridLines: { display: SHOW_GRID },
                            ticks: {
                                beginAtZero: true,
                                callback: function(value) { return value.toLocaleString(); }
                            }
                        }],
                        yAxes: [{
                            stacked: STACKED,
                            beginAtZero: true,
                            scaleLabel: { display: Y_AXIS !== '', labelString: Y_AXIS },
                            gridLines: { display: SHOW_GRID },
                            ticks: {
                                beginAtZero: true,
                                callback: function(value) { return value.toLocaleString(); }
                            }
                        }]
                    },
                    tooltips: {
                        displayColors: false,
                        callbacks: {
                            label: function(tooltipItem, all) {
                                return all.datasets[tooltipItem.datasetIndex].label + ': ' + tooltipItem.yLabel.toLocaleString();
                            }
                        }
                    }
                }
            });
            // 你可以在此分支也增加AI建议请求，方式同上
        });
    }
}
