"""Fitness-matched retrospective timing and invalidation, without training."""
import json
from pathlib import Path
import tempfile
from lisa2.project import DEFAULTS
from lisa2.timing_trial import first_fitness_hit,summarize

root=Path('runs/timing-tests');root.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(dir=root.resolve()) as temp:
    folder=Path(temp);tasks=[]
    cases={'ga':[(0,.1),(10,.5),(20,.49)],'memetic':[(0,.1),(5,.4),(12,.6),(30,.7)]}
    for method,measurements in cases.items():
        project=folder/f'{method}.json';data=folder/f'{method}.data';data.mkdir()
        project.write_text(json.dumps(dict(format='Lisa2 project',version=1,images=['a','b','c','d'],settings=DEFAULTS,data_directory=data.name)))
        rows=[dict(fitness=fitness,wall_seconds=wall,cpu_seconds=wall*.9,loss=1-fitness,status='plateau' if i==len(measurements)-1 else 'running') for i,(wall,fitness) in enumerate(measurements)]
        (data/'timing.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
        (data/'timing-end.json').write_text(json.dumps(dict(wall_seconds=measurements[-1][0])))
        tasks.append(dict(seed=23,method=method,project=str(project)))
    (folder/'protocol.json').write_text(json.dumps(dict(initial_loss=1.,initial_fitness=.1,fitness_tolerance=1e-8,seeds=[23],tasks=tasks,relative_targets=[],equal_quality_rule='min best fitness')))
    summarize(folder);result=json.loads((folder/'results.json').read_text())
    common=result['shared_quality'][0]
    assert common['fitness']==.5 # Best GA fitness, not its final .49.
    assert common['hits']['ga']['wall_seconds']==10
    assert common['hits']['memetic']['wall_seconds']==12
    assert first_fitness_hit([], .1,.1)['wall_seconds']==0
    assert first_fitness_hit([dict(fitness=.2)], .3,.1) is None
    (folder/'INVALIDATED.json').write_text('{}')
    try: summarize(folder);raise AssertionError('Invalid batch accepted')
    except RuntimeError: pass
print('PASS: best-fitness matching, rewind to actual first hit, initial-state zero time and invalid-batch rejection.')
