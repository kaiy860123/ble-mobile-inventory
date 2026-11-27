// Run only inside the connected Artifact Session; all objects remain callback-scoped.
export function addHandoffSlide(presentation, d, index) {
  const s=presentation.slides.add({width:1280,height:720});
  s.background.fill='#FFFFFF';
  function text(value,x,y,w,h,size='21pt',color='#183447',bold=false){
    const a=s.shapes.add({geometry:'textbox',name:`text-${x}-${y}`,position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
    a.text=String(value);a.text.style={fontSize:size,typeface:'Microsoft JhengHei',color,bold,insets:0,autoFit:'none',wrap:'square'};return a;
  }
  text('BLE × GAZEBO  /  INTEGRATION HANDOFF',64,34,1100,30,'13pt','#008B80',true);
  text(d.title,64,86,1152,75,'30pt','#10283F',true);
  text(d.subtitle||'',64,164,1152,45,'18pt','#567080');
  text(`${String(index+1).padStart(2,'0')} / 22`,1120,672,100,26,'13pt','#567080');
  s.speakerNotes.text=(d.notes||'')+'\n\n來源：\n'+d.sources.join('\n');
  const y=222,w=1152,h=430;
  if(d.layout==='table'){
    const values=[d.table.headers,...d.table.rows];
    const tb=s.tables.add({rows:values.length,columns:values[0].length,left:64,top:y,width:w,height:h,values});
    tb.borders.assign({fill:'#D9E5EC',width:1,style:'solid'});
    for(let r=0;r<values.length;r++){
      tb.rows[r].height=h/values.length;
      for(let c=0;c<values[0].length;c++){
        const cell=tb.getCell(r,c);cell.fill=r===0?'#10283F':r%2?'#EFF6F6':'#FFFFFF';
        cell.text.style={fontSize:'17pt',typeface:'Microsoft JhengHei',color:r===0?'#FFFFFF':'#183447',bold:r===0,insets:6};
      }
    }
  }else if(d.layout==='code'){
    const a=text(d.code.text,64,y,w,h,'17pt');a.fill='#EFF5F7';
    a.text.style={fontSize:'17pt',typeface:'Consolas',insets:16,color:'#183447',autoFit:'none'};
  }else if(d.layout==='two-column'){
    d.columns.forEach((c,i)=>{
      text(c.heading,64+i*590,y,555,62,'23pt','#008B80',true);
      c.lines.forEach((line,j)=>text(line,64+i*590,y+75+j*69,550,62,'21pt'));
    });
  }else if(d.layout==='formula'){
    d.formulas.forEach((f,i)=>{
      const yy=y+i*143;
      text(f.expression,64,yy,w,45,'23pt','#008B80',true);
      text(f.meaning,64,yy+49,w,42,'19pt');
      text(f.example||'',64,yy+94,w,40,'18pt','#567080');
    });
  }else if(d.layout==='diagram'){
    const positions=d.id==='S04'?{
      gazebo:[64,240,245,100],core:[390,240,245,100],aws:[710,240,245,100],pages:[1030,240,186,100],
      xiao:[64,470,245,100],store:[710,470,350,100]
    }:{sim:[64,240,270,95],map:[455,240,310,95],api:[910,240,306,95],truth:[455,485,310,95],ctrl:[910,485,306,95]};
    const shapes={};
    d.diagram.nodes.forEach(n=>{
      const p=positions[n.id];const a=text(n.label,...p,'19pt','#10283F',true);a.fill='#EAF4F3';a.text.insets=12;shapes[n.id]=a;
    });
    d.diagram.edges.filter(e=>!(d.id==='S04'&&e.from==='gazebo'&&e.to==='store')).forEach(e=>{
      const from=positions[e.from],to=positions[e.to];
      const downward=to[1]>from[1],upward=to[1]<from[1];
      s.shapes.connect(shapes[e.from],shapes[e.to],{kind:'elbow',fromSide:downward?'bottom':'right',toSide:downward?'top':upward?'bottom':'left',line:{fill:'#008B80',width:2,style:e.label.includes('待')?'dashed':'solid'},tail:{type:'triangle',width:'sm',length:'sm'}});
    });
    // Labels explain protocols; no truth edge is routed through the solver.
    if(d.id==='S04'){
      text('觀測 HTTP',306,205,180,30,'17pt','#008B80');text('TLS 8883',638,205,150,30,'17pt','#008B80');text('WSS 443',963,205,180,30,'17pt','#008B80');
      text('BLE → RPi → 核心（待整合）',64,580,580,32,'17pt','#567080');
      text('Gazebo → truth.jsonl → 離線評估；真值不進入定位輸入',64,622,1140,35,'18pt','#008B80',true);
    }else{
      text('sim_time 與 sequence',65,365,350,40,'18pt','#567080');
      text('同批 UTC 同步寫入真值',455,410,430,40,'18pt','#008B80');
      text('重開模擬先開始新巡查',840,597,376,40,'18pt','#567080');
    }
  }else{
    d.bullets.forEach((line,i)=>{
      const yy=y+i*(h/Math.max(d.bullets.length,1));
      text(String(i+1).padStart(2,'0'),64,yy,70,60,'22pt','#008B80',true);
      text(line,150,yy,1060,75,'23pt');
    });
  }
  return s.id;
}
