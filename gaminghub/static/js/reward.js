function showReward(xp, coins){

let div=document.createElement("div");

div.className="reward-popup";

div.innerHTML=`+${xp} XP<br>+${coins} Coins`;

document.body.appendChild(div);

setTimeout(()=>{

div.remove();

},2500);

}