for i in range(140):
    print(f'temp{i},')



temp_cols = [f"temp{i}" for i in range(140)]
temp_all_cols = ", ".join(temp_cols)    

print(temp_all_cols)